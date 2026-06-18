# This plugin allows you to quickly prepend "sudo" to the current command line by pressing the double Esc key.
sudo-command-line() {
    [[ -z $BUFFER ]] && zle up-history
    if [[ $BUFFER == sudo\ * ]]; then
        LBUFFER="${LBUFFER#sudo }"
    else
        LBUFFER="sudo $LBUFFER"
    fi
}

# Create a new ZLE widget for the sudo-command-line function
zle -N sudo-command-line

# Bind the double Esc key to the sudo-command-line widget
bindkey '\e\e' sudo-command-line
