set nu
set rnu
set scrolloff=10
set expandtab
set smartindent
set shiftwidth=4
set tabstop=4
set softtabstop=4
nnoremap <leader>t :!bun vitest<CR>  " For JS/TS
nnoremap <leader>j :!mvn test<CR>    " For Java
" Exit Vim if NERDTree is the only window remaining in the only tab.
autocmd BufEnter * if tabpagenr('$') == 1 && winnr('$') == 1 && exists('b:NERDTree') && b:NERDTree.isTabTree() | call feedkeys(":quit\<CR>:\<BS>") | endif
autocmd VimEnter * NERDTree
