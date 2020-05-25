#!/usr/bin/env python3

import wx
import os
import sys
import time
import sqlite3
import spotipy
import os
from pygame import mixer
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from spotipy.oauth2 import SpotifyClientCredentials


# Export or SET (for win32) the needed variables for the Spotify Web API
os.environ['SPOTIPY_CLIENT_ID'] = 'bbb9a6588df14fd585de0828d261b899'
os.environ['SPOTIPY_CLIENT_SECRET'] = '7320b96d25b44f78ae22f8bd2aaece8d'
os.environ['SPOTIPY_REDIRECT_URI'] = 'http://127.0.0.1:9090'

# Make database to store files that are currently being played.


def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except sqlite3.Error as e:
        print(e)
        print("Unable to establish connection to database...\n")

    return conn


def insert_into_current(conn, data_field):
    sql = ''' INSERT or REPLACE INTO playlist(title, duration, artist)
              VALUES(?,?,?) '''
    cur = conn.cursor()
    cur.execute(sql, (data_field[0], data_field[1], data_field[2]))


# Currently loaded songs.
currentpl = 'playing.db'


class Scope(wx.Frame):
    def __init__(self, parent, id):

        no_resize = wx.DEFAULT_FRAME_STYLE & ~ (wx.RESIZE_BORDER |
                                                wx.MAXIMIZE_BOX)

        super().__init__(
            None, title="Scope", style=no_resize, size=(1000, 1000), pos=(0, 0))
        self.SetBackgroundColour("White")
        self.panel = wx.Panel(self, size=(500, 500))
        self.panel.SetBackgroundColour("Black")

        # Panel for playlist listbox and filter options.
        self.plbox = wx.Panel(self, size=(500, 500))
        self.plbox.SetBackgroundColour("Red")

        # Menubar settings.
        menubar = wx.MenuBar()
        filemenu = wx.Menu()
        open = wx.MenuItem(filemenu, wx.ID_OPEN, '&Open')
        exit = wx.MenuItem(filemenu, wx.ID_CLOSE, '&Exit')
        add = wx.MenuItem(filemenu, wx.ID_OPEN, '&Add to playlist')
        filemenu.Append(open)
        filemenu.Append(add)
        filemenu.Append(exit)
        menubar.Append(filemenu, '&File')
        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU, self.menuhandler)

        # Sizer for different panels.
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.panel, flag=wx.EXPAND | wx.ALL)
        sizer.Add(self.plbox, flag=wx.EXPAND | wx.ALL)
        self.SetSizer(sizer)
        self.Center()

    # Function to handle menubar options.
    def menuhandler(self, event):
        id = event.GetId()
        ev = event.GetString()
        if id == wx.ID_OPEN:
            with wx.FileDialog(self.panel, "Open Image file", wildcard="Music files (*.mp3,*.wav,*.aac,*.ogg,*.flac)|*.mp3;*.wav;*.aac;*.ogg;*.flac",
                               style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file:

                if file.ShowModal() == wx.ID_CANCEL:
                    return

                self.pathname = file.GetPath()
                try:
                    # TODO Allow the loading of the file

                    self.loadfile(self.pathname)
                    self.playlistd(self.pathname)
                except IOError:
                    wx.LogError("Cannot open file '%s'." % newfile)

        if id == wx.ID_CLOSE:
            self.Close()

        if ev == "Add to playlist":
            # TODO add option to add pathnames to listbox.
            with wx.FileDialog(self.panel, "Open Image file", wildcard="Music files (*.mp3,*.wav,*.aac,*.ogg,*.flac)|*.mp3;*.wav;*.aac;*.ogg;*.flac",
                               style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file:

                if file.ShowModal() == wx.ID_CANCEL:
                    return

                self.pathnameforpl = file.GetPath()
                try:
                    # TODO Allow the loading of the file
                    self.playlistd(self.pathnameforpl)

                except IOError:
                    wx.LogError("Cannot open file '%s'." % newfile)

    def loadfile(self, path):
        # TODO implement file load
        s = 4

    def playlistd(self, path):
        # TODO Implement playlist adding to playing now.
        self.curr_pl = create_connection(currentpl)
        self.curr_pl.execute('''CREATE TABLE IF NOT EXISTS playlist
        (title VARCHAR(255) UNIQUE,
        duration VARCHAR(255),
        artist VARCHAR(255))''')

        self.curr_pl.commit()
        song_data = []
        song_data = self.getMutagenTags(path)
        insert_into_current(self.curr_pl, song_data)

    def getMutagenTags(self, path):

        audio = ID3(path)

        print("Artist: %s" % audio['TPE1'].text[0])
        print("Track: %s" % audio["TIT2"].text[0])
        print("Release Year: %s" % audio["TDRC"].text[0])

        self.makeCover(audio['TIT2'].text[0])
        data = []

        # Insert song data in list for inserting in database of currently playing songs.
        data.append(audio["TIT2"].text[0])
        song = MP3(path)
        d = int(song.info.length)
        minutes = d // 60
        seconds = d % 60
        duration = str(minutes) + ":" + str(seconds)
        data.append(duration)
        data.append(audio['TPE1'].text[0])

        return data

    # TODO make possible to put id3 data in database.

    def makeCover(self, track_name):

        spotify = spotipy.Spotify(
            client_credentials_manager=SpotifyClientCredentials())

        # Gets album art cover by track name.
        result = spotify.search(q=track_name, limit=20)
        for track in result['tracks']['items']:
            print(track['album']['images'][0]['url'])
            break


app = wx.App()
frame = Scope(None, -1)
frame.Show()
app.MainLoop()
