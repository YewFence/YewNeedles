_tm_smart_run() {
    case "$1" in
        clean)
            # Kill all tmux sessions except the current one, or kill the tmux server if not in a session
            if [ -n "$TMUX" ]; then
                local current=$(tmux display-message -p '#S')
                local session

                tmux list-sessions -F '#S' | grep -F -x -v -- "$current" | while IFS= read -r session; do
                    tmux kill-session -t "$session"
                done
                echo "🧹 Clean all sessions except [$current]"
            else
                if tmux kill-server 2>/dev/null; then
                    echo "🧹 Clean all sessions (tmux server killed)"
                else
                    echo "There are no active tmux servers to kill."
                fi
            fi
            ;;
        *)
            # if argument provided, attach or create session with that name
            if [ -z "$1" ]; then
                tmux attach || tmux new-session
            else
                tmux new-session -A -s "$1"
            fi
            ;;
    esac
}

# main command
tm() {
    _tm_smart_run "$@"
}
