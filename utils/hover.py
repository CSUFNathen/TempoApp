# utils/hover.py
def add_hover_effect(button, normal_color, hover_color):
    """
    Simple hover: only change fg_color. Avoid font tweaks that can resize
    the button and trigger extra <Configure> events.
    """
    def on_enter(_):
        try:
            button.configure(fg_color=hover_color)
        except Exception:
            pass

    def on_leave(_):
        try:
            button.configure(fg_color=normal_color)
        except Exception:
            pass

    button.bind("<Enter>", on_enter)
    button.bind("<Leave>", on_leave)
