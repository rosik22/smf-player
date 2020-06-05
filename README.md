# smf-player

**This is a simple music file player for a project.**
**The project is a joint effort between me and [rosik22](https://www.github.com/rosik22 "rosik22") for a University project.**

The player is written in Python. It has the option to save and open playlists. You may also load folders.
ID3 tag reading is part of its forte along with loading album art covers wherever possible via the LastFM API and it offers 
song recommendations via Spotify's Web API.

More can be said but it's best to try it out. The GUI is written in wxPython.



![Image of player](https://github.com/roterabe/smf-player/blob/master/example.png)



# Usage

First install all prerequisites by running:

`pip3 install prerequisites.txt` or `pip install prerequisites`

You then may install wxPython separately if you're on Windows or MacOS by running:

`pip3 install wxPython` or `pip install wxPython`

**If you're on Linux:**

For Debian based:

`pip install -U \`
`    -f https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-16.04 \`
`    wxPython`

For Arch based:

`sudo pacman -Syu wxPython`

For RHL based:

`pip install -U \`
`    -f https://extras.wxpython.org/wxPython4/extras/linux/gtk3/fedora-30/ \`
`    wxPython`


And finally. You'll need to supply your own API keys for AcoustID, LastFM and Spotify.

You'll need to input them here:

![Place for API keys](https://github.com/roterabe/smf-player/blob/master/example.png)