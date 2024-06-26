set history=500

set rtp+=~/.vim/bundle/Vundle.vim
call vundle#begin()

filetype plugin on
filetype indent on

set autoread
au FocusGained,BufEnter * checktime

set ruler
set cmdheight=1
set cursorline

set backspace=eol,start,indent
set whichwrap+=<,>,h,l

set background=dark
set encoding=utf8
set ffs=unix,dos,mac

set tabstop=4
set shiftwidth=4

syntax on
set nu
set ai
set si
set wrap

" tabs
nnoremap tf  :tabfirst<CR>
nnoremap tn  :tabnext<CR>
nnoremap tp  :tabprev<CR>
nnoremap tl  :tablast<CR>
nnoremap tm  :tabm<Space>
nnoremap tc  :tabclose<CR>


au BufReadPost * if line("'\"") > 1 && line("'\"") <= line("$") | exe "normal! g'\"" | endif
set laststatus=2

" Format the status line
set statusline=\ %{HasPaste()}%F%m%r%h\ %w\ \ CWD:\ %r%{getcwd()}%h\ \ \Line:\ %l\ \ Column:\ %c


" py
au BufNewFile,BufRead *.py
    \ set tabstop=4 |
    \ set softtabstop=4 |
    \ set shiftwidth=4 |
    \ set textwidth=79 |
    \ set expandtab |
    \ set autoindent |
    \ set fileformat=unix
    \ set colorcolumn=80


" functions
function! HasPaste()
    if &paste
        return 'PASTE MODE  '
    endif
    return ''
endfunction


" Plugins
Plugin 'VundleVim/Vundle.vim'
Plugin 'davidhalter/jedi-vim'
Plugin 'mattn/emmet-vim'
Plugin 'rust-lang/rust.vim'
Plugin 'tpope/vim-fugitive'
Plugin 'morhetz/gruvbox'
Plugin 'preservim/nerdtree'


call vundle#end()            " required
filetype plugin indent on    " required

set background=dark
let g:gruvbox_contrast_dark='hard'
colorscheme gruvbox
hi Normal guibg=NONE ctermbg=NONE


