## How to install Python on macOS

macOS will prompt you to install pip when you first try using it, however the way macOS installs it can cause issues. *So if you have issues*, I recommend using Homebrew instead.

1. Remove old installation

```
sudo rm -rf /Library/Developer/CommandLineTools
```

2. Install Homebrew

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

3. Install Python

```
brew install python
```

4. Install todo-txt-tui

```
pip3 install todo-txt-tui
```

## "zsh: command not found: todo-txt-tui"

If you get this error even if TodoTxtTUI is installed, you need to update your PATH.

1. `touch ~/.zshrc`
2. `echo 'export PATH="$HOME/Library/Python/3.8/bin:$PATH"' >> ~/.zshrc`
   * Replace `3.8` with correct version
3. `source ~/.zshrc`
4. `todo-txt-tui`

If you use Bash, replace `.zshrc` with `.bashrc`.