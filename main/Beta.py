#!/usr/bin/env python3

import wx
import wx.media
import os
import sys
import time
import sqlite3
import spotipy
from functools import partial
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from mutagen import File as MutaFile
from spotipy.oauth2 import SpotifyClientCredentials

# Export or SET (for win32) the needed variables for the Spotify Web API
os.environ['SPOTIPY_CLIENT_ID'] = 'bbb9a6588df14fd585de0828d261b899'
os.environ['SPOTIPY_CLIENT_SECRET'] = '7320b96d25b44f78ae22f8bd2aaece8d'
os.environ['SPOTIPY_REDIRECT_URI'] = 'http://127.0.0.1:9090'

# Currently loaded songs.
currentpl = 'playing.db'

class Scope(wx.Frame):
    def __init__(self, parent, id):

        no_resize = wx.DEFAULT_FRAME_STYLE & ~ (wx.RESIZE_BORDER |
                                                wx.MAXIMIZE_BOX)
        super().__init__(
            None, title="Scope", style=no_resize, size=(600, 800), pos=(0, 0))

        self.establishConnection()

        self.SetBackgroundColour("White")
        self.panel = wx.Panel(self, size=(500, 200))
        self.panel.SetBackgroundColour("Black")

        # Panel for playlist listbox and filter options.
        self.plbox = wx.Panel(self, size=(500, 600))
        self.playlistBox = wx.ListCtrl(self.plbox, size=(500, 450), pos=(50, 50), style=wx.LC_REPORT)
        self.playlistBox.AppendColumn("Artist", width=200)
        self.playlistBox.AppendColumn("Title", width=200)
        self.playlistBox.AppendColumn("Duration", width=100)
        self.playlistBox.Bind(wx.EVT_LIST_ITEM_SELECTED, self.loadSongFromListBox)
        self.plbox.SetBackgroundColour("White")

        self.createMenu()
        self.createLayout()
        self.Buttons()

        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Center()
#-----------------------------------------------------------------------------------------------------------------------#
    def OnClose(self, e):
        self.conn.close()
        self.Destroy()

#-----------------------------------------------------------------------------------------------------------------------#
    # Menubar settings.
    def createMenu(self):
        menubar = wx.MenuBar()
        filemenu = wx.Menu()
        open1 = filemenu.Append(-1, "&Open")
        add = filemenu.Append(-1, "&Add to playlist")
        exit2 = filemenu.Append(-1, "&Exit")
        menubar.Append(filemenu, '&File')
        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU, partial(self.menuhandler, 1), open1)
        self.Bind(wx.EVT_MENU, partial(self.menuhandler, 2), add)
        self.Bind(wx.EVT_MENU, partial(self.menuhandler, 3), exit2)

#-----------------------------------------------------------------------------------------------------------------------#
    # Function to handle menubar options.
    def menuhandler(self,num ,event):
        id = event.GetId()
        if num == 1:
            with wx.FileDialog(self.panel, "Open Music file", wildcard="Music files (*.mp3,*.wav,*.aac,*.ogg,*.flac)|*.mp3;*.wav;*.aac;*.ogg;*.flac",
                               style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file:

                if file.ShowModal() == wx.ID_CANCEL:
                    return

                pathname = file.GetPath()
                
                try:
                    self.curs.execute('DELETE FROM playlist;')
                    self.conn.commit()
                    self.playlistBox.DeleteAllItems()
                    self.Player.Load(pathname)
                    self.getMutagenTags(pathname)
                except IOError:
                    wx.LogError("Cannot open file '%s'." % pathname)

        elif num == 2:
            with wx.FileDialog(self.panel, "Open Image file", wildcard="Music files (*.mp3,*.wav,*.aac,*.ogg,*.flac)|*.mp3;*.wav;*.aac;*.ogg;*.flac",
                               style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file:

                if file.ShowModal() == wx.ID_CANCEL:
                    return

                pathname = file.GetPath()
                
                try:
                    if self.Player.Length() == -1:
                        self.Player.Load(pathname)
                    self.getMutagenTags(pathname)
                except IOError:
                    wx.LogError("Cannot open file '%s'." % pathname)

        elif num == 3:
            self.Close()

#-----------------------------------------------------------------------------------------------------------------------#
    # Sets the layout
    def createLayout(self):
        try:
            self.Player = wx.media.MediaCtrl(self, style=wx.SIMPLE_BORDER)
        except NotImplementedError:
            self.Destroy()
            raise

        self.PlayerSlider = wx.Slider(self.panel, size=wx.DefaultSize,)
        self.PlayerSlider.Bind(wx.EVT_SLIDER, self.OnSeek)

        # Sizer for different panels.
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.panel, flag=wx.EXPAND | wx.ALL)
        sizer.Add(self.plbox, flag=wx.EXPAND | wx.ALL)
        self.SetSizer(sizer)

#-----------------------------------------------------------------------------------------------------------------------#
    def loadSongFromListBox(self, e):
        d = []
        row = e.GetEventObject().GetFocusedItem()
        count = self.playlistBox.GetItemCount()
        cols = self.playlistBox.GetColumnCount()
        for col in range(cols-1):
            item = self.playlistBox.GetItem(itemIdx=row, col=col)
            d.append(item.GetText())

        artistName = str(d[0])
        songTitle = str(d[1])

        self.curs.execute('''SELECT path FROM playlist WHERE artist=? AND title=? ''', (artistName,songTitle))
        path = ''.join(self.curs.fetchone())
        
        self.Player.Load(path)
        self.Player.Play()
        self.ButtonPlay.SetValue(True)

#-----------------------------------------------------------------------------------------------------------------------#
    def Buttons(self):
        picPlayBtn = wx.Bitmap("play-button.png", wx.BITMAP_TYPE_ANY)
        self.ButtonPlay = wx.BitmapToggleButton(
            self.panel, label=picPlayBtn, pos=(100, 100))
        self.ButtonPlay.SetInitialSize()
        self.ButtonPlay.Bind(wx.EVT_TOGGLEBUTTON, self.OnPlay)

#-----------------------------------------------------------------------------------------------------------------------#
    def getMutagenTags(self, path):
        audio = ID3(path)
        song = MutaFile(path)
        d = int(song.info.length)
        data = []

        # Insert song data in list for inserting in database of currently playing songs.
        minutes = d // 60
        seconds = d % 60
        duration = str(minutes) + ":" + str(seconds)

        data.append(audio["TIT2"].text[0]) #title
        data.append(duration)
        data.append(audio['TPE1'].text[0]) #artist
        data.append(str(audio["TDRC"].text[0])) #year
        data.append(path)

        self.playlistd(data)
        self.fillPlaylistBox(data)

#-----------------------------------------------------------------------------------------------------------------------#
    def fillPlaylistBox(self,data):
        list1 = (data[2],data[0],data[1])
        self.playlistBox.InsertItem(0, list1[0])
        self.playlistBox.SetItem(0, 1, str(list1[1]))
        self.playlistBox.SetItem(0, 2, str(list1[2]))

#-----------------------------------------------------------------------------------------------------------------------#
    def establishConnection(self):
        self.conn = None
        try:
            self.conn = sqlite3.connect(currentpl)
        except sqlite3.Error as e:
            print(e)
            print("Unable to establish connection to database...\n")

        self.curs = self.conn.cursor()
        self.createTable()

#-----------------------------------------------------------------------------------------------------------------------#
    def createTable(self):
        self.curs.execute('''CREATE TABLE IF NOT EXISTS playlist
                            (title VARCHAR(255) UNIQUE,
                            duration VARCHAR(255),
                            artist VARCHAR(255),
                            year VARCHAR(255),
                            path VARCHAR(255))''')
        self.curs.execute('DELETE FROM playlist;')
        self.conn.commit()

#-----------------------------------------------------------------------------------------------------------------------#
    def playlistd(self, data):
        self.curs.execute('''REPLACE INTO playlist(title,duration,artist,year,path) 
                    VALUES(?,?,?,?,?)''', (data[0],data[1],data[2],data[3],data[4]))
        self.conn.commit()

#-----------------------------------------------------------------------------------------------------------------------#
    def makeCover(self, track_name):

        spotify = spotipy.Spotify(
            client_credentials_manager=SpotifyClientCredentials())

        # Gets album art cover by track name.
        result = spotify.search(q=track_name, limit=20)
        for track in result['tracks']['items']:
            print(track['album']['images'][0]['url'])
            break

#-----------------------------------------------------------------------------------------------------------------------#
    def OnPause(self):
        self.Player.Pause()

    def OnPlay(self, event):
        if not event.GetEventObject().GetValue():
            self.OnPause()
            return

        if not self.Player.Play():
            self.ButtonPlay.SetValue(False)
            wx.MessageBox("A file must be selected.",
                          "ERROR", wx.ICON_ERROR | wx.OK)

        else:
            self.PlayerSlider.SetRange(0, self.Player.Length())

    def OnSeek(self, event):
        self.Player.Seek(self.PlayerSlider.GetValue())


app = wx.App()
frame = Scope(None, -1)
frame.Show()
app.MainLoop()
