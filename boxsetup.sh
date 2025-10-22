#!/usr/bin/env bash

# boxsetup.sh - Universal machine setup script
# Supports: Linux (Debian/Ubuntu, RHEL/Fedora), macOS, FreeBSD, OpenBSD

set -euo pipefail

# Configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly BACKUP_DIR="${SCRIPT_DIR}/configs_backup_$(date +%Y%m%d_%H%M%S)"
readonly DOTFILES_REPO="${DOTFILES_REPO:-https://github.com/yourusername/dotfiles}"
readonly DOTFILES_BRANCH="${DOTFILES_BRANCH:-master}"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Flags
DRY_RUN=false
VERBOSE=false
INTERACTIVE=false
SKIP_PACKAGES=false
SKIP_DOTFILES=false

# OS and package manager variables
OS_TYPE=""
OS_DIST=""
PKG_MANAGER=""
PKG_INSTALL=""
PKG_UPDATE=""

# Logging functions
log() {
    local level="$1"
    shift
    local message="$*"
    
    case "${level}" in
        ERROR)
            echo -e "${RED}[ERROR]${NC} ${message}" >&2
            ;;
        WARNING)
            echo -e "${YELLOW}[WARNING]${NC} ${message}" >&2
            ;;
        INFO)
            echo -e "${GREEN}[INFO]${NC} ${message}"
            ;;
        DEBUG)
            [[ "${VERBOSE}" == true ]] && echo -e "${BLUE}[DEBUG]${NC} ${message}"
            ;;
    esac
}

error() {
    log ERROR "$@"
    exit 1
}

warning() {
    log WARNING "$@"
}

info() {
    log INFO "$@"
}

debug() {
    log DEBUG "$@"
}

# Usage function
usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Universal machine setup script for Linux, macOS, FreeBSD, and OpenBSD.

OPTIONS:
    -h, --help          Show this help message
    -d, --dry-run       Show what would be done without making changes
    -v, --verbose       Enable verbose output
    -i, --interactive   Run in interactive mode (ask before each step)
    -s, --skip-packages Skip package installation
    -S, --skip-dotfiles Skip dotfiles installation
    -r, --repo URL      Specify dotfiles repository URL
    -b, --branch NAME   Specify dotfiles branch (default: master)

EXAMPLES:
    $(basename "$0")                    # Run full setup
    $(basename "$0") -d                 # Dry run to preview changes
    $(basename "$0") -i                 # Interactive mode
    $(basename "$0") --skip-packages    # Only install dotfiles

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)
                usage
                exit 0
                ;;
            -d|--dry-run)
                DRY_RUN=true
                info "Running in DRY RUN mode"
                ;;
            -v|--verbose)
                VERBOSE=true
                ;;
            -i|--interactive)
                INTERACTIVE=true
                ;;
            -s|--skip-packages)
                SKIP_PACKAGES=true
                ;;
            -S|--skip-dotfiles)
                SKIP_DOTFILES=true
                ;;
            -r|--repo)
                shift
                DOTFILES_REPO="$1"
                ;;
            -b|--branch)
                shift
                DOTFILES_BRANCH="$1"
                ;;
            *)
                error "Unknown option: $1"
                ;;
        esac
        shift
    done
}

# Confirmation prompt
confirm() {
    local prompt="$1"
    local response
    
    if [[ "${INTERACTIVE}" != true ]]; then
        return 0
    fi
    
    echo -n "${prompt} [y/N]: "
    read -r response
    case "${response}" in
        [yY][eE][sS]|[yY])
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# OS Detection
detect_os() {
    info "Detecting operating system..."
    
    if [[ -f /etc/os-release ]]; then
        # Linux
        . /etc/os-release
        OS_TYPE="linux"
        OS_DIST="${ID}"
        
        case "${OS_DIST}" in
            ubuntu|debian)
                PKG_MANAGER="apt"
                PKG_INSTALL="apt-get install -y"
                PKG_UPDATE="apt-get update"
                ;;
            fedora)
                PKG_MANAGER="dnf"
                PKG_INSTALL="dnf install -y"
                PKG_UPDATE="dnf check-update || true"
                ;;
            centos|rhel|rocky|almalinux)
                if command -v dnf >/dev/null 2>&1; then
                    PKG_MANAGER="dnf"
                    PKG_INSTALL="dnf install -y"
                    PKG_UPDATE="dnf check-update || true"
                else
                    PKG_MANAGER="yum"
                    PKG_INSTALL="yum install -y"
                    PKG_UPDATE="yum check-update || true"
                fi
                ;;
            arch|manjaro)
                PKG_MANAGER="pacman"
                PKG_INSTALL="pacman -S --noconfirm"
                PKG_UPDATE="pacman -Sy"
                ;;
            *)
                warning "Unknown Linux distribution: ${OS_DIST}"
                ;;
        esac
        
    elif [[ "$(uname)" == "Darwin" ]]; then
        # macOS
        OS_TYPE="macos"
        OS_DIST="macos"
        PKG_MANAGER="brew"
        PKG_INSTALL="brew install"
        PKG_UPDATE="brew update"
        
    elif [[ "$(uname)" == "FreeBSD" ]]; then
        # FreeBSD
        OS_TYPE="freebsd"
        OS_DIST="freebsd"
        PKG_MANAGER="pkg"
        PKG_INSTALL="pkg install -y"
        PKG_UPDATE="pkg update"
        
    elif [[ "$(uname)" == "OpenBSD" ]]; then
        # OpenBSD
        OS_TYPE="openbsd"
        OS_DIST="openbsd"
        PKG_MANAGER="pkg_add"
        PKG_INSTALL="pkg_add"
        PKG_UPDATE="true"  # No update command for pkg_add
        
    else
        error "Unsupported operating system: $(uname)"
    fi
    
    info "Detected: ${OS_TYPE} (${OS_DIST}) with ${PKG_MANAGER}"
}

# Check if running as root (when needed)
check_root() {
    if [[ "${OS_TYPE}" == "linux" ]] || [[ "${OS_TYPE}" == "freebsd" ]] || [[ "${OS_TYPE}" == "openbsd" ]]; then
        if [[ $EUID -ne 0 ]] && [[ "${PKG_MANAGER}" != "brew" ]]; then
            error "This script must be run as root on ${OS_TYPE}"
        fi
    fi
}

# Install Homebrew on macOS if not present
install_homebrew() {
    if [[ "${OS_TYPE}" == "macos" ]] && ! command -v brew >/dev/null 2>&1; then
        info "Installing Homebrew..."
        if [[ "${DRY_RUN}" == true ]]; then
            echo "[DRY RUN] Would install Homebrew"
        else
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
    fi
}

# Update package manager
update_packages() {
    if [[ "${SKIP_PACKAGES}" == true ]]; then
        debug "Skipping package manager update"
        return
    fi
    
    if ! confirm "Update package manager?"; then
        info "Skipping package manager update"
        return
    fi
    
    info "Updating package manager..."
    if [[ "${DRY_RUN}" == true ]]; then
        echo "[DRY RUN] Would run: ${PKG_UPDATE}"
    else
        eval "${PKG_UPDATE}"
    fi
}

# Read package list from configuration
get_package_list() {
    local pkg_file="${SCRIPT_DIR}/packages.conf"
    
    if [[ ! -f "${pkg_file}" ]]; then
        debug "No packages.conf found, using defaults"
        # Default package list
        case "${OS_TYPE}" in
            linux|freebsd|openbsd)
                echo "vim tmux git curl wget zsh htop"
                ;;
            macos)
                echo "vim tmux git curl wget zsh htop coreutils"
                ;;
        esac
    else
        # Parse INI-style config file
        local packages=""
        local common_packages=""
        local os_packages=""
        local distro_packages=""
        
        # Function to read packages from a specific section
        read_section() {
            local section_name="$1"
            local in_section=false
            local section_packages=""
            
            while IFS= read -r line; do
                # Skip empty lines
                [[ -z "${line// }" ]] && continue
                
                # Check for section headers
                if [[ "${line}" =~ ^\[([^\]]+)\]$ ]]; then
                    if [[ "${BASH_REMATCH[1]}" == "${section_name}" ]]; then
                        in_section=true
                    else
                        in_section=false
                    fi
                elif [[ "${in_section}" == true ]]; then
                    # Add package to list
                    section_packages="${section_packages} ${line}"
                fi
            done < "${pkg_file}"
            
            echo "${section_packages}"
        }
        
        # Read common packages (always included)
        common_packages=$(read_section "common")
        
        # Read OS-specific packages
        os_packages=$(read_section "${OS_TYPE}")
        
        # Read distro-specific packages (if different from OS type)
        if [[ "${OS_DIST}" != "${OS_TYPE}" ]]; then
            distro_packages=$(read_section "${OS_DIST}")
        fi
        
        # Combine all packages (common + os + distro)
        packages="${common_packages} ${os_packages} ${distro_packages}"
        
        echo "${packages}"
    fi
}

# Install packages
install_packages() {
    if [[ "${SKIP_PACKAGES}" == true ]]; then
        debug "Skipping package installation"
        return
    fi
    
    if ! confirm "Install packages?"; then
        info "Skipping package installation"
        return
    fi
    
    local packages=$(get_package_list)
    
    if [[ -z "${packages}" ]]; then
        info "No packages to install"
        return
    fi
    
    info "Installing packages: ${packages}"
    
    for package in ${packages}; do
        debug "Installing ${package}..."
        if [[ "${DRY_RUN}" == true ]]; then
            echo "[DRY RUN] Would run: ${PKG_INSTALL} ${package}"
        else
            if eval "${PKG_INSTALL} ${package}"; then
                info "Successfully installed ${package}"
            else
                warning "Failed to install ${package}"
            fi
        fi
    done
}

# Backup existing configuration files before appending
backup_configs() {
    local files=(".vimrc" ".tmux.conf" ".bashrc" ".zshrc" ".gitconfig")
    local backup_needed=false
    
    for file in "${files[@]}"; do
        if [[ -f "${HOME}/${file}" ]]; then
            backup_needed=true
            break
        fi
    done
    
    if [[ "${backup_needed}" == false ]]; then
        debug "No existing configs to backup"
        return
    fi
    
    info "Backing up existing configuration files before installation..."
    
    if [[ "${DRY_RUN}" == true ]]; then
        echo "[DRY RUN] Would create backup directory: ${BACKUP_DIR}"
    else
        mkdir -p "${BACKUP_DIR}"
    fi
    
    for file in "${files[@]}"; do
        if [[ -f "${HOME}/${file}" ]]; then
            if [[ "${DRY_RUN}" == true ]]; then
                echo "[DRY RUN] Would backup: ${HOME}/${file} to ${BACKUP_DIR}/${file}"
            else
                cp "${HOME}/${file}" "${BACKUP_DIR}/${file}"
                info "Backed up ${file}"
            fi
        fi
    done
}

# Clone or update dotfiles repository
clone_dotfiles() {
    # Use local dotfiles from current directory instead of cloning
    info "Using local dotfiles from ${SCRIPT_DIR}/dotfiles..."
    return 0
}

# Detect current shell and install appropriate configurations
detect_and_install_shell_config() {
    local current_shell=$(basename "${SHELL}")
    local dotfiles_dir="${SCRIPT_DIR}/dotfiles"
    
    info "Detected current shell: ${current_shell}"
    
    case "${current_shell}" in
        zsh)
            if [[ -f "${dotfiles_dir}/zshrc" ]]; then
                install_config_file "zshrc"
            fi
            ;;
        bash)
            if [[ -f "${dotfiles_dir}/bashrc" ]]; then
                install_config_file "bashrc"
            fi
            ;;
        *)
            warning "Unknown shell: ${current_shell}, installing both bash and zsh configs"
            [[ -f "${dotfiles_dir}/bashrc" ]] && install_config_file "bashrc"
            [[ -f "${dotfiles_dir}/zshrc" ]] && install_config_file "zshrc"
            ;;
    esac
}

# Install a single configuration file
install_config_file() {
    local file="$1"
    local dotfiles_dir="${SCRIPT_DIR}/dotfiles"
    local source="${dotfiles_dir}/${file}"
    local target="${HOME}/.${file}"
    
    if [[ ! -f "${source}" ]]; then
        debug "Source file not found: ${source}"
        return
    fi
    
    if [[ "${DRY_RUN}" == true ]]; then
        if [[ -f "${target}" ]]; then
            echo "[DRY RUN] Would append ${source} to existing ${target}"
        else
            echo "[DRY RUN] Would copy ${source} to ${target}"
        fi
    else
        if [[ -f "${target}" ]]; then
            # Check if already contains our configuration
            if grep -q "# Added by boxsetup.sh" "${target}" 2>/dev/null; then
                info "Configuration already added to ${file}, skipping"
                return
            fi
            
            # Append to existing file
            info "Appending ${file} to existing configuration"
            echo "" >> "${target}"
            echo "# Added by boxsetup.sh on $(date)" >> "${target}"
            cat "${source}" >> "${target}"
            info "Appended ${file} to existing configuration"
        else
            # Copy new file
            cp "${source}" "${target}"
            info "Installed ${file}"
        fi
    fi
}

# Copy dotfiles to their target locations
copy_dotfiles() {
    local dotfiles_dir="${SCRIPT_DIR}/dotfiles"
    local files_to_copy=("vimrc" "tmux.conf" "gitconfig")
    
    info "Installing dotfiles..."
    
    # Check if dotfiles directory exists
    if [[ ! -d "${dotfiles_dir}" ]]; then
        error "Dotfiles directory not found: ${dotfiles_dir}"
    fi
    
    # Install shell-specific configuration
    detect_and_install_shell_config
    
    # Install other configuration files
    for file in "${files_to_copy[@]}"; do
        install_config_file "${file}"
    done
}

# Install Vundle for Vim if needed
install_vundle() {
    local vundle_dir="${HOME}/.vim/bundle/Vundle.vim"
    
    if [[ -f "${SCRIPT_DIR}/dotfiles/vimrc" ]] && ! [[ -d "${vundle_dir}" ]]; then
        info "Installing Vundle for Vim..."
        if [[ "${DRY_RUN}" == true ]]; then
            echo "[DRY RUN] Would install Vundle to ${vundle_dir}"
        else
            git clone https://github.com/VundleVim/Vundle.vim.git "${vundle_dir}"
            info "Vundle installed successfully"
        fi
    fi
}

# Install dotfiles
install_dotfiles() {
    if [[ "${SKIP_DOTFILES}" == true ]]; then
        debug "Skipping dotfiles installation"
        return
    fi
    
    if ! confirm "Install dotfiles?"; then
        info "Skipping dotfiles installation"
        return
    fi
    
    backup_configs
    clone_dotfiles
    install_vundle
    copy_dotfiles
}

# Post-installation setup
post_install() {
    info "Running post-installation setup..."
    
    # Set zsh as default shell if installed
    if command -v zsh >/dev/null 2>&1; then
        if confirm "Set zsh as default shell?"; then
            if [[ "${DRY_RUN}" == true ]]; then
                echo "[DRY RUN] Would change shell to zsh"
            else
                if chsh -s "$(command -v zsh)" 2>/dev/null; then
                    info "Changed default shell to zsh"
                else
                    warning "Could not change shell automatically. You may need to run: chsh -s $(command -v zsh)"
                fi
            fi
        fi
    fi
    
    # Install vim plugins if vim is configured
    if [[ -f "${HOME}/.vimrc" ]] && command -v vim >/dev/null 2>&1; then
        if confirm "Install vim plugins?"; then
            if [[ "${DRY_RUN}" == true ]]; then
                echo "[DRY RUN] Would install vim plugins"
            else
                vim +PluginInstall +qall
                info "Installed vim plugins"
            fi
        fi
    fi
}

# Main execution
main() {
    echo "========================================="
    echo "        Box Setup Script v1.0"
    echo "========================================="
    
    # Parse arguments
    parse_args "$@"
    
    # Detect OS
    detect_os
    
    # Check root privileges if needed
    check_root
    
    # Install Homebrew on macOS if needed
    [[ "${OS_TYPE}" == "macos" ]] && install_homebrew
    
    # Update package manager
    update_packages
    
    # Install packages
    install_packages
    
    # Install dotfiles
    install_dotfiles
    
    # Post-installation setup
    post_install
    
    info "Setup completed successfully!"
    
    if [[ -d "${BACKUP_DIR}" ]]; then
        info "Existing configs backed up to: ${BACKUP_DIR}"
    fi
    
    echo "========================================="
    echo "  Please restart your terminal session"
    echo "========================================="
}

# Run main function
main "$@"