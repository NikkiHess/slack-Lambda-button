#!/usr/bin/env python3

"""
The TKinter GUI module for Slack-Lambda-Button.

Author:
Nikki Hess - nkhess@umich.edu
"""

import time

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkFont

import sys
import threading # for sqs polling

from PIL import Image, ImageTk

is_simpleaudio_installed = True
try:
    import simpleaudio as sa
except ImportError as e:
    print("WARNING: SimpleAudio is not installed, audio will not play")
    is_simpleaudio_installed = False

import slack
import aws
import sheets
import auto_updater

MAIZE = "#FFCB05"
BLUE = "#00274C"
PRESS_START = None # for long button presses

pending_message_ids = [] # pending messages from this device specifically
message_to_channel = {} # maps message ids to channel ids

pending_message_ids_lock = threading.Lock()

frames = []
frames_ready = False
frames_lock = threading.Lock()

LOGGING_SHEETS_SERVICE, LOGGING_SPREADSHEET_ID = None, None
CONFIG_SHEETS_SERVICE, CONFIG_SPREADSHEET_ID = None, None

if is_simpleaudio_installed:
    INTERACT_SOUND = sa.WaveObject.from_wave_file("audio/send.wav")
    RECEIVE_SOUND = sa.WaveObject.from_wave_file("audio/receive.wav")
    RATELIMIT_SOUND = sa.WaveObject.from_wave_file("audio/ratelimit.wav")
    RESOLVED_SOUND = sa.WaveObject.from_wave_file("audio/resolved.wav")

def preload_frames_lazy(root: tk.Tk):
    """
    Preloads and caches images lazily.
    First frame available immediately, others load in the background.
    
    Args:
        root (tk.Tk): The root window.
    """
    global frames, frames_ready

    frame_count = 149

    base = {"width": 1920, "height": 1080}
    actual = {"width": root.winfo_screenwidth(), "height": root.winfo_screenheight()}
    scale = min(actual["width"] / base["width"], actual["height"] / base["height"])

    with Image.open("images/custom-animation-fix.gif") as gif:
        gif.seek(0)
        with frames_lock: # lock to prevent race conditions (not guaranteed)
            frames.append(load_and_scale_image(root, gif.copy(), scale))

    def worker():
        global frames_ready
        with Image.open("images/custom-animation-fix.gif") as gif:
            for i in range(1, frame_count):
                try:
                    gif.seek(i)
                    with frames_lock: # lock in case of race conditions (not guaranteed)
                        frames.append(load_and_scale_image(root, gif.copy(), scale))
                except EOFError:
                    # if we can't load any more frames, get outta here
                    break
        frames_ready = True

    threading.Thread(target=worker, daemon=True).start()


def bind_presses(root: tk.Tk, frame: tk.Frame, style: ttk.Style, do_post: bool) -> None:
    """
    A simple function to bind or rebind button press-release events for TKinter

    Args:
        root (tk.Tk): the root window
        frame (tk.Frame): the frame we're currently working with
        style (ttk.Style): the style manager for our window
        do_post (bool): whether to post to Slack
    """

    # long presses exit the app
    def handle_long_press():
        if time.time() - PRESS_START >= 3:
            exit(0)

    root.bind("<ButtonPress-1>", lambda event: handle_interaction(root, frame, style, do_post))
    root.bind("<ButtonRelease-1>", lambda event: handle_long_press())

def scale_font(root: tk.Tk, base_size: int) -> int:
    """
    Scales a font based on the size of the window

    Args:
        root (tk.Tk): the root window
        base_size (int): the size of the text at 1080p

    Returns:
        int: the scaled font's size
    """
    base = {"width": 1920, "height": 1080}
    actual = {"width": root.winfo_screenwidth(), "height": root.winfo_screenheight()}

    calculated_scale = min(actual["width"] / base["width"], actual["height"] / base["height"])

    return int(calculated_scale * base_size)

def load_and_scale_image(root: tk.Tk, img: Image.Image, scale: float) -> ImageTk.PhotoImage:
    """
    Uses PIL to rescale an image based on the size of the window

    Args:
        root (tk.Tk): the root window
        image_path (str): the image to load and scale
        scale (float): the new scale for the image

    Returns:
        ImageTk.PhotoImage: the scaled PhotoImage for TKinter
    """

    new_size = (int(scale * img.width), int(scale * img.height))
    resized_image = img.resize(new_size, Image.Resampling.BILINEAR) # BILINEAR is faster than LANCZOS
    photo_image = ImageTk.PhotoImage(resized_image)

    return photo_image

def display_main(frame: tk.Frame, style: ttk.Style) -> None:
    """
    Displays the main (idle) screen for the user

    Args:
        frame (tk.Frame): the frame we're working with
        style (ttk.Style): the style manager for our window
    """

    def load_contents():
        oswald_96 = tkFont.Font(family="Oswald", size=scale_font(frame, 96), weight="bold")
        oswald_80 = tkFont.Font(family="Oswald", size=scale_font(frame, 80), weight="bold")

        style.configure("NeedHelp.TLabel", foreground=MAIZE, background=BLUE, font=oswald_96)
        style.configure("Instructions.TLabel", foreground=MAIZE, background=BLUE, font=oswald_80)

        dude_img_label = ttk.Label(frame, image=frames[0], background=BLUE)
        dude_img_label.place(relx=0.5, rely=0.34, anchor="center")

        frame_count = len(frames)

        # poll frames_ready to wait for frames to load
        def start_animation():
            if len(frames) < 2:
                # wait for at least 2 frames to start
                frame.after(50, start_animation)
                return

            def update(index: int):
                if index >= len(frames):
                    # stop at the last frame
                    return
                dude_img_label.configure(image=frames[index])
                frame.after(20, update, index + 1)

            update(0)


        start_animation()

        instruction_label = ttk.Label(frame, text="Tap the screen!",
                                    style="Instructions.TLabel")
        instruction_label.place(relx=0.5, rely=0.71+.06, anchor="center")

        # help label has to be rendered after img to be seen (layering)
        help_label = ttk.Label(frame, text="Need help?", style="NeedHelp.TLabel")
        help_label.place(relx=0.5, rely=0.57+.06, anchor="center")

    load_contents()

def handle_interaction(root: tk.Tk, frame: tk.Frame, style: ttk.Style,
                       do_post: bool) -> None:
    """
    Handles the Lambda function and switching to the post-interaction display

    Args:
        root (tk.Tk): the root window
        frame (tk.Frame): the frame that we're putting widgets in
        style (ttk.Style): the style manager for our window
        do_post (bool): whether or not to post to the Slack channel
    """
    global PRESS_START
    PRESS_START = time.time()

    def worker():
        message_id, channel_id = slack.handle_interaction(
            slack.lambda_client, do_post
        )

        def gui_update():
            if message_id != "statusCode":
                # clear display and switch frames
                for widget in frame.winfo_children():
                    widget.place_forget()

                root.unbind("<ButtonPress-1>")
                bind_presses(root, frame, style, False)

                display_post_interaction(root, frame, style, do_post)

                with pending_message_ids_lock:
                    pending_message_ids.append(message_id)
                message_to_channel[message_id] = channel_id

                if is_simpleaudio_installed:
                    INTERACT_SOUND.play()
            elif do_post:
                ratelimit_label = ttk.Label(frame, text="Rate limit applied. Please wait before tapping again.",
                                            style="Escape.TLabel")
                ratelimit_label.place(relx=0.5, rely=0.99, anchor="s")
                if is_simpleaudio_installed:
                    RATELIMIT_SOUND.play()
                root.after(3 * 1000, fade_label, root,
                           ratelimit_label, hex_to_rgb(MAIZE), hex_to_rgb(BLUE), 0, 1500)

        root.after(0, gui_update)

    threading.Thread(target=worker, daemon=True).start()

def display_post_interaction(root: tk.Tk, frame: tk.Frame, style: ttk.Style, do_post: bool) -> None:
    """
    Displays the post interaction instructions

    Args:
        root (tk.Tk): the root window
        frame (tk.Frame): the frame
        style (ttk.Style): the style manager for our window
        do_post (bool): whether to post to Slack
    """

    base_timeout = 180

    # countdown
    timeout = base_timeout

    oswald_96 = tkFont.Font(family="Oswald", size=scale_font(root, 96), weight="bold")
    oswald_80 = tkFont.Font(family="Oswald", size=scale_font(root, 80), weight="bold")
    oswald_36 = tkFont.Font(family="Oswald", size=scale_font(root, 36), weight="bold")
    monospace = tkFont.Font(family="Ubuntu Mono", size=scale_font(root, 36), weight="bold")

    # make a BG frame so nothing else shows through
    background_frame = tk.Frame(frame, bg=BLUE)
    background_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

    # create a text widget to display the countdown and timeout
    text_widget = tk.Text(frame, background=BLUE, foreground=MAIZE, bd=0,
                          highlightthickness=0, selectbackground=BLUE)
    text_widget.place(relx=0.996, rely=0.99, anchor="se", relheight=0.07, relwidth=0.355)

    # configure tags for different fonts
    text_widget.tag_configure("timeout", font=oswald_36, foreground=MAIZE)
    text_widget.tag_configure("countdown", font=monospace, foreground=MAIZE)

    # configure tag for right justification
    text_widget.tag_configure("right", justify="right")
    text_widget.tag_add("right", "1.0", "end")

    def update_text_widget():
        if not text_widget.winfo_exists():
            return
        
        text_widget.config(state=tk.NORMAL) # enable editing

        text_widget.delete("1.0", tk.END)

        text_widget.insert(tk.END, f"{' ' if timeout < 100 else ''}", "countdown")
        text_widget.insert(tk.END, "Request times out in ", "timeout")
        text_widget.insert(tk.END, f"{timeout}", "countdown")
        text_widget.insert(tk.END, " seconds", "timeout")

        text_widget.config(state=tk.DISABLED) # disable editing

    # Initial update
    update_text_widget()

    polling_thread = threading.Thread(target=aws.poll_sqs,
                                      args=[aws.SQS_CLIENT, slack.BUTTON_CONFIG["device_id"]],
                                      daemon=True)
    polling_thread.start()

    # this helps determine whether we've received a reply later
    reply_received = False

    # do a timeout countdown
    def countdown():
        nonlocal timeout, reply_received
        nonlocal root, frame, style, do_post

        # decrement seconds left and set the label's text
        timeout -= 1
        update_text_widget()

        # if we have a message from SQS, make sure it's ours and then use it
        if aws.LATEST_MESSAGE:
            ts = aws.LATEST_MESSAGE["ts"]
            reply_author = aws.LATEST_MESSAGE["reply_author"]
            reply_text = aws.LATEST_MESSAGE["reply_text"]

            with pending_message_ids_lock:
                if ts in pending_message_ids:
                    # if no resolving reaction/emoji, display message
                    if not "white_check_mark" in reply_text and not "+1" in reply_text:
                        received_label.configure(text="")
                        waiting_label.configure(text=f"From {reply_author}\n" + reply_text)
                        waiting_label.place_configure(rely=0.5)

                        aws.LATEST_MESSAGE = None

                        # bump the timer up if necessary
                        if timeout <= base_timeout // 3 + 1:
                            timeout = base_timeout // 3 + 1

                        # make sure the system knows we replied but
                        # still allow for multi-replies
                        reply_received = True

                        # if we've received a reply mark it replied
                        message_id = pending_message_ids[0]
                        channel_id = message_to_channel[message_id]
                        aws.mark_message_replied(slack.lambda_client, message_id, channel_id, True)

                        if is_simpleaudio_installed:
                            RECEIVE_SOUND.play()
                    # else revert to main and cancel this countdown
                    else:
                        sheets_button_config = slack.get_config(CONFIG_SHEETS_SERVICE,
                                                                CONFIG_SPREADSHEET_ID,
                                                                slack.BUTTON_CONFIG["device_id"])
                        
                        threading.Thread(target=sheets.add_row, args=(LOGGING_SHEETS_SERVICE, LOGGING_SPREADSHEET_ID,
                                                                        [
                                                                        slack.get_datetime(),
                                                                        sheets_button_config[3], # gets location
                                                                        "Resolved"
                                                                        ]
                                                                    ),
                                                                daemon=True
                                        ).start()

                        revert_to_main(root, frame, style, do_post)
                        
                        if is_simpleaudio_installed:
                            RESOLVED_SOUND.play()

                        aws.LATEST_MESSAGE = None

        if timeout <= 0:
            revert_to_main(root, frame, style, do_post)

            sheets_button_config = slack.get_config(CONFIG_SHEETS_SERVICE,
                                                    CONFIG_SPREADSHEET_ID,
                                                    slack.BUTTON_CONFIG["device_id"])
            threading.Thread(target=sheets.add_row, args=(LOGGING_SHEETS_SERVICE, LOGGING_SPREADSHEET_ID,
                                                            [
                                                            slack.get_datetime(),
                                                            sheets_button_config[3], # gets location
                                                            "Replied" if reply_received else "Timed Out"
                                                            ]
                                                         ),
                                                         daemon=True
                            ).start()

            # if we have a pending message or haven't received a reply,
            # we need to time out
            with pending_message_ids_lock:
                if len(pending_message_ids) > 0 and not reply_received:
                    message_id = pending_message_ids[0]
                    channel_id = message_to_channel[message_id]

                    aws.mark_message_timed_out(slack.lambda_client, message_id, channel_id, True)

        # schedule countdown until seconds_left is 1
        if timeout > 0:
            root.after(1000, countdown)
        else:
            aws.STOP_THREAD = True
            return

    root.after(1000, countdown)

    received_label = tk.Label(frame,
                            text="Help is on the way!",
                            font=oswald_96,
                            fg=MAIZE,
                            bg=BLUE,
                            anchor="center",
                            justify="center"
                            )
    received_label.place(relx=0.5, rely=0.40, anchor="center")

    waiting_label = tk.Label(frame,
                            text="Updates will be provided on this screen.",
                            font=oswald_80,
                            fg=MAIZE,
                            bg=BLUE,
                            anchor="center",
                            justify="center"
                            )
    waiting_label.configure(wraplength=root.winfo_screenwidth())
    waiting_label.place(relx=0.5, rely=0.60, anchor="center")

    root.update_idletasks() # gets stuff to load all at once

def revert_to_main(root: tk.Tk, frame: tk.Frame, style: ttk.Style, do_post: bool) -> None:
    """
    Reverts from another frame to the main display

    Args:
        root (tk.Tk): the root window we're working with
        frame (tk.Frame): the frame we're working with
        style (ttk.Style): the style we'd like to hold onto
        do_post (bool): whether to post to Slack
    """

    for widget in frame.winfo_children():
        widget.destroy()

    # restore left click bindings
    bind_presses(root, frame, style, do_post)

    display_main(frame, style)

def hex_to_rgb(hex_str: str) -> tuple:
    """
    Converts a hex string (#000000) to an RGB tuple ((0, 0, 0))

    Args:
        hex_str (str): the hex string to convert

    Returns:
        tuple: what our hex converts to
    """

    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

# https://stackoverflow.com/questions/57337718/smooth-transition-in-tkinter
def interpolate(start_color: tuple, end_color: tuple, time_: int) -> tuple:
    """
    Interpolates between two colors based on time

    Args:
        start_color (tuple): the color to start with
        end_color (tuple): the color to end with
        time_ (int): the amount of time that has passed

    Returns:
        An interpolated tuple somewhere between our two colors
    """
    return tuple(int(a + (b - a) * time_) for a, b in zip(start_color, end_color))

# https://stackoverflow.com/questions/57337718/smooth-transition-in-tkinter
def fade_label(frame: tk.Tk, label: ttk.Label, start_color: tuple, end_color: tuple,
               current_step: int, fade_duration_ms: int) -> None:
    """
    A recursive function that fades a label from one color to another

    Args:
        root (tk.Tk): the root of the window
        label (ttk.Label): the label to fade
        start_color (tuple): the start color, as an RGB tuple
        end_color (tuple): the end color, as an RGB tuple
        current_step (int): for recursion, tells the function how much we've faded
        fade_duration_ms (int): the length of time to fade for, in MS
    """

    # set a framerate for the fade
    fps = 30

    time_ = (1.0 / fps) * current_step
    current_step += 1

    new_color = interpolate(start_color, end_color, time_)
    label.configure(foreground=f"#{new_color[0]:02x}{new_color[1]:02x}{new_color[2]:02x}")

    if current_step <= fps:
        frame.after(fade_duration_ms // fps, fade_label, frame,
                   label, start_color, end_color, current_step,
                   fade_duration_ms)

def setup_logging():
    """
    Runs the sheets function to set up logging,
    then sets the globals LOGGING_SHEETS_SERVICE + SPREADSHEET_ID
    """
    global LOGGING_SHEETS_SERVICE, LOGGING_SPREADSHEET_ID, CONFIG_SHEETS_SERVICE
    global CONFIG_SPREADSHEET_ID

    _, sheets_service, _, _, spreadsheet_id = sheets.setup_sheets("google_logging")
    LOGGING_SHEETS_SERVICE = sheets_service
    LOGGING_SPREADSHEET_ID = spreadsheet_id

    _, sheets_service, _, _, spreadsheet_id = sheets.setup_sheets("google_config")
    CONFIG_SHEETS_SERVICE = sheets_service
    CONFIG_SPREADSHEET_ID = spreadsheet_id

def display_gui() -> None:
    """
    Displays the TKinter GUI. Essentially the main function
    """

    escape_display_period_ms = 5000
    do_post = True

    # make a window
    root = tk.Tk()
    root.config(cursor="none")

    root.attributes("-fullscreen", True)
    root.configure(bg=BLUE)
    root.title("Slack Lambda Button")

    display_frame = tk.Frame(root, bg=BLUE)
    display_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

    # configure style
    style = ttk.Style()

    # bind keys/buttons
    root.bind("<Escape>", lambda event: root.destroy())
    bind_presses(root, display_frame, style, do_post)

    # if is_raspberry_pi:
    #     setup_gpio(root, display_frame, style, do_post)

    preload_frames_lazy(root)

    display_main(display_frame, style)

    # load oswald, a U of M standard font
    oswald_42 = tkFont.Font(family="Oswald", size=scale_font(root, 42), weight="bold")

    style.configure("Escape.TLabel", foreground=MAIZE, background=BLUE, font=oswald_42)

    # set up the actual items in the display
    escape_label = ttk.Label(display_frame, text="Press escape or long press to exit", style="Escape.TLabel")
    escape_label.place(relx=0.99, rely=0.99, anchor="se")

    # Fade the escape label out
    root.after(escape_display_period_ms, fade_label, root,
               escape_label, hex_to_rgb(MAIZE), hex_to_rgb(BLUE), 0, 1500)

    # run the auto updater
    interval_seconds = 15 * 60 # every 15 minutes

    thread = threading.Thread(target=auto_updater.do_auto_update, args=(interval_seconds,), daemon=True)
    thread.start()

    # run
    root.mainloop()

if __name__ == "__main__":
    slack.get_datetime(True)
    setup_logging()

    display_gui()
