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

syntax on
set nu
set ai
set si
set wrap

" tabs
map <leader>tn :tabnew<cr>
map <leader>to :tabonly<cr>
map <leader>tc :tabclose<cr>
map <leader>tm :tabmove
map <leader>t<leader> :tabnext
map <leader>te :tabedit <C-r>=expand("%:p:h")<cr>/

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


call vundle#end()            " required
filetype plugin indent on    " required
