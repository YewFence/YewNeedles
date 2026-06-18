# This Zsh plugin allows you to automatically add a space at the beginning of a command when you press the Alt + s key combination.
# Open the history ignore space option
setopt HIST_IGNORE_SPACE

# Define the function for automatically adding spaces
space-command-line() {
    # If the command already starts with a space, remove it
    if [[ $BUFFER == \ * ]]; then
        LBUFFER="${LBUFFER# }"
    else
        # Otherwise, add a space at the beginning of the command
        LBUFFER=" $LBUFFER"
    fi
}

# Create a new ZLE widget for the space-command-line function
zle -N space-command-line

# Bind the Alt + s key to the space-command-line widget
bindkey '\es' space-command-line
