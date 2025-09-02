#!/bin/bash

# Bash completion for ec2.py
# Installation: source this file in your .bashrc or copy to /etc/bash_completion.d/

_ec2_complete() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    # Get the directory where ec2.py is located
    local ec2_script="${COMP_WORDS[0]}"
    
    # First argument - commands
    if [[ ${COMP_CWORD} -eq 1 ]]; then
        opts="list ssh showconfig"
        COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
        return 0
    fi
    
    # Second argument for ssh command - instance names
    if [[ ${COMP_CWORD} -eq 2 ]] && [[ "${COMP_WORDS[1]}" == "ssh" ]]; then
        # Get instance names from cache
        local instances=$("${ec2_script}" list --format names 2>/dev/null)
        if [[ -n "${instances}" ]]; then
            COMPREPLY=($(compgen -W "${instances}" -- ${cur}))
        fi
        return 0
    fi
    
    # Options
    case "${prev}" in
        -r|--region)
            # Common AWS regions
            local regions="us-east-1 us-east-2 us-west-1 us-west-2 eu-west-1 eu-west-2 eu-central-1 ap-northeast-1 ap-southeast-1 ap-southeast-2"
            COMPREPLY=($(compgen -W "${regions}" -- ${cur}))
            return 0
            ;;
        -u|--user)
            # Common SSH users
            local users="ec2-user ubuntu centos admin root"
            COMPREPLY=($(compgen -W "${users}" -- ${cur}))
            return 0
            ;;
        -i|--key)
            # SSH key files
            COMPREPLY=($(compgen -f -- ${cur}))
            return 0
            ;;
        *)
            ;;
    esac
    
    # General options
    opts="--region --all-regions --no-cache --user --key --port --tmux --no-tmux --access-key --secret-key --help"
    COMPREPLY=($(compgen -W "${opts}" -- ${cur}))
}

# Register completion for ec2.py
complete -F _ec2_complete ec2.py
# Also register for ./ec2.py
complete -F _ec2_complete ./ec2.py
# Register for full path
if [[ -f /Users/zidoo/Projects/dotfiles/scripts/ec2.py ]]; then
    complete -F _ec2_complete /Users/zidoo/Projects/dotfiles/scripts/ec2.py
fi