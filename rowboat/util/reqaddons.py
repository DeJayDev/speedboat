from pygal.style import Style

class DiscordStyle(Style):
    """A Discord Style based off CleanStyle style"""

    # Fuck it, settin da fields
    background = 'rgb(43,46,51)' 
    plot_background = 'rgb(43,46,51)'

    font_family = 'googlefont:roboto'

    foreground = 'rgb(255, 255, 255)'
    foreground_strong = 'rgb(255, 255, 255)'
    foreground_subtle = 'rgb(255, 255, 255)'
    colors = (
        'rgb(114,137,218)', 'rgb(114,137,218)', 'rgb(114,137,218)', 
        'rgb(114,137,218)', 'rgb(114,137,218)', 'rgb(114,137,218)',
        'rgb(114,137,218)', 'rgb(114,137,218)', 'rgb(114,137,218)'
    )
