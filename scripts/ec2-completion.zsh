#!/bin/zsh

# Zsh completion for ec2.py
# Installation: Add to your .zshrc or copy to ~/.zsh/completions/

_ec2_complete() {
    local state
    
    _arguments \
        '1: :->command' \
        '2: :->target' \
        '-r[AWS region]:region:(us-east-1 us-east-2 us-west-1 us-west-2 eu-west-1 eu-west-2 eu-central-1 ap-northeast-1 ap-southeast-1 ap-southeast-2)' \
        '--region[AWS region]:region:(us-east-1 us-east-2 us-west-1 us-west-2 eu-west-1 eu-west-2 eu-central-1 ap-northeast-1 ap-southeast-1 ap-southeast-2)' \
        '-a[List all regions]' \
        '--all-regions[List all regions]' \
        '--no-cache[Force refresh]' \
        '-u[SSH user]:user:(ec2-user ubuntu centos admin root)' \
        '--user[SSH user]:user:(ec2-user ubuntu centos admin root)' \
        '-i[SSH key file]:keyfile:_files' \
        '--key[SSH key file]:keyfile:_files' \
        '-p[SSH port]:port:' \
        '--port[SSH port]:port:' \
        '--tmux[Force tmux window]' \
        '--no-tmux[Disable tmux]' \
        '--access-key[AWS Access Key]:key:' \
        '--secret-key[AWS Secret Key]:key:' \
        '--format[Output format]:format:(names table)' \
        '--help[Show help]'
    
    case $state in
        command)
            local commands
            commands=(
                'list:List EC2 instances'
                'ssh:SSH to an instance'
                'showconfig:Show configuration'
            )
            _describe 'command' commands
            ;;
        target)
            case ${words[2]} in
                ssh)
                    # Get instance names for SSH command
                    local instances
                    instances=(${(f)"$(${words[1]} list --format names 2>/dev/null)"})
                    if [[ -n "$instances" ]]; then
                        _describe 'instance' instances
                    fi
                    ;;
                list)
                    # For list command, just provide hint
                    _message 'name pattern (optional)'
                    ;;
            esac
            ;;
    esac
}

# Find ec2.py in common locations
if [[ -f /Users/zidoo/Projects/dotfiles/scripts/ec2.py ]]; then
    compdef _ec2_complete /Users/zidoo/Projects/dotfiles/scripts/ec2.py
fi
compdef _ec2_complete ec2.py
compdef _ec2_complete ./ec2.py
