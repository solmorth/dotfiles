return {
  "preservim/nerdtree",
  config = function()
    -- Optionally set keymaps to toggle NERDTree
    vim.api.nvim_set_keymap('n', '<leader>n', ':NERDTreeToggle<CR>', { noremap = true, silent = true })
  end,
  lazy = false -- or true if you want to lazy load
}
