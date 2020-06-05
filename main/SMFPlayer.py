#!/usr/bin/env python3

import wx
import wx.media
import os
import sys
import time
import sqlite3
import acoustid
import urllib.request
import urllib.parse
import json
import spotipy
import wave
import contextlib
import re
from spotipy.oauth2 import SpotifyClientCredentials
from acoustid import fingerprint_file
from xml.dom.minidom import parseString
from PIL import Image
from functools import partial
from io import BytesIO
from shutil import copyfile
from mutagen.id3 import ID3
from mutagen import File as MutaFile

os.environ['SPOTIPY_CLIENT_ID'] = 'set-client-id-here'
os.environ['SPOTIPY_CLIENT_SECRET'] = 'set-client-secret-here'
os.environ['SPOTIPY_REDIRECT_URI'] = 'set-client-uri-here'

# Set LastFM key here.
lkey = ''

# Set acoustid key here.
akey = ''

# Currently loaded songs.
currentpl = 'playing.db'


class Ultra(wx.Frame):
    def __init__(self, parent, id):

        no_resize = wx.DEFAULT_FRAME_STYLE & ~ (wx.RESIZE_BORDER |
                                                wx.MAXIMIZE_BOX)
        super().__init__(
            None, title="smf-player", style=no_resize, size=(1300, 800), pos=(0, 0))

        # Establish connection with the databases
        self.establishConnectionRun()
        # self.establishConnectionRating()

        # Set self color.
        self.SetBackgroundColour("Black")

        # Counter for listctrl when adding additional files.
        self.countListCttl = 0
        self.countAddToPlaylist = 0

        # Playback panel
        self.panel = wx.Panel(self, size=(700, 200))
        self.panel.SetBackgroundColour("Black")

        # Panel for album cover
        self.display = wx.Panel(self, size=(700, 600))
        self.display.SetBackgroundColour("Black")
        self.disp = wx.StaticBitmap(
            self.display, size=(500, 500), pos=(100, 50))
        self.artist_name = ''
        self.song_name = ''

        # Panel for playlist listbox and filter options.
        self.plbox = wx.Panel(self, size=(600, 500))
        self.plbox.SetBackgroundColour("SALMON")
        # listctrl for the loaded songs
        self.playlistBox = wx.ListCtrl(self.plbox, size=(
            550, 425), pos=(25, 10), style=wx.LC_REPORT)
        self.playlistBox.AppendColumn("Artist", width=170)
        self.playlistBox.AppendColumn("Title", width=170)
        self.playlistBox.AppendColumn("Duration", width=70)
        self.playlistBox.AppendColumn("Counter", width=70)
        self.playlistBox.AppendColumn("Rating", width=70)
        self.playlistBox.SetBackgroundColour("Black")
        self.playlistBox.SetTextColour("White")
        self.playlistBox.Bind(wx.EVT_LIST_ITEM_SELECTED,
                              self.loadSongFromListBox)

        # Panel for song recommendations.
        self.rec = wx.Panel(self, size=(600, 300))
        self.rec.SetBackgroundColour("SALMON")
        # listctrl for the recomended songs
        self.recBox = wx.ListCtrl(self.rec, size=(
            550, 220), pos=(25, 0), style=wx.LC_REPORT)
        self.recBox.AppendColumn("Artist", width=200)
        self.recBox.AppendColumn("Title", width=200)
        self.recBox.AppendColumn("Duration", width=150)
        self.recBox.SetBackgroundColour("Black")
        self.recBox.SetTextColour("White")
        self.recBox.Bind(wx.EVT_LIST_ITEM_SELECTED,
                         self.loadSongFromRecommendationBox)
        self.recommendations = []

        # Timer for the playback scroll.
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer)
        self.timer.Start(50)

        # Create menu on top left of application.
        self.createMenu()

        # Assign panels to sizers.
        self.createLayout()

        # Create playback and functionality buttons.
        self.Buttons()

        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Center()

#-----------------------------------------------------------------------------------------------------------------------#
    # Steps to do after closing window. Like disconnecting from db.
    def OnClose(self, e):
        self.conn1.close()
        self.Player.SetVolume(1.0)
        self.Destroy()

#-----------------------------------------------------------------------------------------------------------------------#
    # Menubar settings.
    def createMenu(self):
        menubar = wx.MenuBar()
        filemenu = wx.Menu()
        helpmenu = wx.Menu()

        # Appending options in file menu.
        open1 = filemenu.Append(-1, '&Open')
        openf = filemenu.Append(-1, '&Open folder')
        add = filemenu.Append(-1, '&Add to playlist')
        openpl = filemenu.Append(-1, '&Open Playlist')
        savepl = filemenu.Append(-1, '&Save Playlist')
        exit2 = filemenu.Append(-1, '&Exit')

        # Appending "about" info in help menu.
        about = helpmenu.Append(-1, "&About")

        menubar.Append(filemenu, '&File')
        menubar.Append(helpmenu, "&Help")
        self.SetMenuBar(menubar)

        # Using partial to recognize which option has been chosen.
        self.Bind(wx.EVT_MENU, partial(self.menuhandler, 1), openf)
        self.Bind(wx.EVT_MENU, partial(self.menuhandler, 2), open1)
        self.Bind(wx.EVT_MENU, partial(self.menuhandler, 3), add)
        self.Bind(wx.EVT_MENU, partial(self.menuhandler, 4), exit2)
        self.Bind(wx.EVT_MENU, partial(self.menuhandler, 5), savepl)
        self.Bind(wx.EVT_MENU, partial(self.menuhandler, 6), openpl)
        self.Bind(wx.EVT_MENU, partial(self.menuhandler, 7), about)

#-----------------------------------------------------------------------------------------------------------------------#
    # Function to handle menubar options.
    def menuhandler(self, num, event):
        id = event.GetId()

        # Open folder.
        if num == 1:
            with wx.DirDialog(self.panel, "Open Music Dir", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as directory:

                if directory.ShowModal() == wx.ID_CANCEL:
                    return

                pathname = directory.GetPath()
                self.countListCttl = 0

                # Load data on blank space.
                try:
                    self.curs1.execute('DELETE FROM playlist;')
                    self.conn1.commit()
                    self.countAddToPlaylist += 1
                    self.playlistBox.DeleteAllItems()
                    self.clearPanel()
                    self.clearRecommendationBox()

                    # Search for all files in given path and load them with GetMutagenTags.
                    self.loadFolder(pathname)
                except:
                    print("Error during loading the path and/or files within...")

        # Open file and clear playlist.
        elif num == 2:
            with wx.FileDialog(self.panel, "Open Music file", wildcard="Music files (*.mp3,*.wav,*.aac,*.ogg,*.flac)|*.mp3;*.wav;*.aac;*.ogg;*.flac",
                               style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file:

                if file.ShowModal() == wx.ID_CANCEL:
                    return

                pathname = file.GetPath()
                self.countListCttl = 0

                # Clear all boxes and load current file by pathname.
                try:
                    self.curs1.execute('DELETE FROM playlist;')
                    self.conn1.commit()
                    self.playlistBox.DeleteAllItems()
                    self.countAddToPlaylist += 1
                    self.Player.Load(pathname)
                    self.getMutagenTags(pathname)
                    self.playlistBox.SetItemState(
                        0, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED)
                    self.playlistBox.Select(0, on=1)
                    self.PlayerSlider.SetRange(0, self.Player.Length())
                except IOError:
                    wx.LogError("Cannot open file '%s'." % pathname)

        # Add file or files to playlist.
        elif num == 3:
            with wx.FileDialog(self.panel, "Add music file to playlist", wildcard="Music files (*.mp3,*.wav,*.aac,*.ogg,*.flac)|*.mp3;*.wav;*.aac;*.ogg;*.flac",
                               style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE) as file:

                if file.ShowModal() == wx.ID_CANCEL:
                    return

                pathname = file.GetPath()
                pathnames = file.GetPaths()

        # Open just a single file path.
            if len(pathnames) == 1:
                try:
                    self.getMutagenTags(pathname)
                    if self.playlistBox.GetItemCount() == 1:
                        self.playlistBox.SetItemState(
                            0, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED)
                        self.playlistBox.Select(0, on=1)
                    if self.countAddToPlaylist < 1:
                        self.makeCover(
                            self.song_name, self.artist_name, pathname)
                        self.countAddToPlaylist += 1
                    self.PlayerSlider.SetRange(0, self.Player.Length())
                except IOError:
                    wx.LogError("Cannot open file '%s'." % pathname)

        # Open multiple file paths.
            elif len(pathnames) > 1:
                try:
                    if self.playlistBox.GetItemCount() == 0:
                        self.loadFiles(pathnames)
                        self.playlistBox.SetItemState(
                            0, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED)
                        self.playlistBox.Select(0, on=1)
                    if self.playlistBox.GetItemCount() >= 1:
                        self.loadFiles(pathnames)
                    if self.countAddToPlaylist < 1:
                        self.makeCover(
                            self.song_name, self.artist_name, pathname)
                        self.countAddToPlaylist += 1
                    self.PlayerSlider.SetRange(0, self.Player.Length())
                except IOError:
                    wx.LogError("Cannot open file '%s'." % pathname)

        # Close application.
        elif num == 4:
            self.Close()

        # Save playlist to another *.db file for later use.
        elif num == 5:
            with wx.FileDialog(self.panel, "Save playlist", wildcard="Playlist file (*.db)|*.db", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as file:

                if file.ShowModal() == wx.ID_CANCEL:
                    return

                if self.playlistBox.GetItemCount() >= 1:
                    savedfile = file.GetPath()
                    savedfile1 = os.path.split(savedfile)
                    savedfile1 = savedfile1[-1]
                    if '.' not in savedfile1:
                        savedfile += '.db'
                    currfile = copyfile('playing.db', savedfile)

        # Open a playlist *.db file
        elif num == 6:
            with wx.FileDialog(self.panel, "Open playlist file", wildcard="Playlist files (*.db)|*.db", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file:

                if file.ShowModal() == wx.ID_CANCEL:
                    return

                # Get path of *.db file
                pathname = file.GetPath()
                self.playlistBox.DeleteAllItems()
                self.clearRecommendationBox()
                self.countListCttl = 0
                self.countAddToPlaylist = 0

                # Connect to playlist file and load all paths.
                self.establishConnectionPl(pathname)
                pathnames = self.loadPlaylist()

                if len(pathnames) == 1:
                    try:
                        self.getMutagenTags(pathname)
                        if self.playlistBox.GetItemCount() == 1:
                            self.playlistBox.SetItemState(
                                0, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED)
                            self.playlistBox.Select(0, on=1)
                        if self.countAddToPlaylist < 1:
                            self.makeCover(
                                self.song_name, self.artist_name, pathname)
                            self.countAddToPlaylist += 1
                        self.PlayerSlider.SetRange(0, self.Player.Length())
                    except IOError:
                        wx.LogError("Cannot open file '%s'." % pathname)
                elif len(pathnames) > 1:
                    try:
                        self.loadFiles(pathnames)
                        self.makeCover(
                            self.song_name, self.artist_name, pathnames[0])
                        self.playlistBox.SetItemState(
                            0, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED)
                        self.playlistBox.Select(0, on=1)
                        self.countAddToPlaylist += 1
                        self.PlayerSlider.SetRange(0, self.Player.Length())
                    except IOError:
                        wx.LogError("Cannot open file '%s'." % pathname)

        # Show about info.
        elif num == 7:

            info = wx.MessageDialog(
                self.panel, "Smf-Player is free for use and covered by the GNU v3.0 license.", "Smf-Player ver 0.01", wx.OK | wx.CENTER,)
            info.ShowModal()


#-----------------------------------------------------------------------------------------------------------------------#
    # Sets the layout for the player.

    def createLayout(self):
        try:
            self.Player = wx.media.MediaCtrl(self, style=wx.SIMPLE_BORDER)
        except NotImplementedError:
            self.Destroy()
            raise

        self.PlayerSlider = wx.Slider(
            self.panel, style=wx.SL_HORIZONTAL, size=(400, -1), pos=(150, 10))
        self.PlayerSlider.Bind(wx.EVT_SLIDER, self.OnSeek, self.PlayerSlider)

        # filter
        filters = ['Artist', 'Title']
        self.combo = wx.ComboBox(self.plbox, choices=filters, pos=(355, 450))
        self.enterPref = wx.TextCtrl(
            self.plbox, size=(100, 34), pos=(245, 450))

        # Slider for volume
        self.currentVolume = 100
        self.volumeCtrl = wx.Slider(
            self.panel, style=wx.SL_HORIZONTAL, size=(100, -1), pos=(450, 40))
        self.volumeCtrl.SetRange(0, 100)
        self.volumeCtrl.SetValue(100)
        self.Player.SetVolume(1.0)
        self.volumeCtrl.Bind(wx.EVT_SLIDER, self.onVolume, self.volumeCtrl)

        # Sizer for different panels.
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        s1 = wx.BoxSizer(wx.VERTICAL)
        s2 = wx.BoxSizer(wx.VERTICAL)

        s1.Add(self.display, flag=wx.EXPAND | wx.ALL)
        s1.Add(self.panel, flag=wx.EXPAND | wx.ALL)
        s2.Add(self.plbox, flag=wx.EXPAND | wx.ALL)
        s2.Add(self.rec, flag=wx.EXPAND | wx.ALL)

        sizer.Add(s1)
        sizer.Add(s2)
        self.SetSizer(sizer)

#-----------------------------------------------------------------------------------------------------------------------#
    # Creates the buttons and their bindings
    def Buttons(self):
        self.FilterBtn = wx.Button(
            self.plbox, label="Filter", size=(100, 30), pos=(475, 453))

        choices = ['1', '2', '3', '4', '5']
        self.RatingBtns = wx.RadioBox(self.plbox, -1, "Rating", pos=(25, 440),
                                      size=(180, 45), choices=choices, style=wx.RA_HORIZONTAL)
        self.RatingBtns.SetForegroundColour((40, 40, 40))

        picPlayBtn = wx.Bitmap("play-button.png", wx.BITMAP_TYPE_ANY)
        picPlayBtn = self.scaleBitmap(picPlayBtn)

        picPrevBtn = wx.Bitmap("previous-song-button.png", wx.BITMAP_TYPE_ANY)
        picPrevBtn = self.scaleBitmap(picPrevBtn)

        picNextBtn = wx.Bitmap("next-song-button.png", wx.BITMAP_TYPE_ANY)
        picNextBtn = self.scaleBitmap(picNextBtn)

        picRepeatBtn = wx.Bitmap("repeat-button.png", wx.BITMAP_TYPE_ANY)
        picRepeatBtn = self.scaleBitmap(picRepeatBtn)

        self.ButtonPlay = wx.BitmapToggleButton(
            self.panel, label=picPlayBtn, pos=(325, 40))

        self.ButtonPrev = wx.BitmapButton(
            self.panel, bitmap=picPrevBtn, pos=(260, 40))

        self.ButtonNext = wx.BitmapButton(
            self.panel, bitmap=picNextBtn, pos=(390, 40))

        self.ButtonRepeat = wx.BitmapToggleButton(
            self.panel, label=picRepeatBtn, pos=(195, 40))

        self.ButtonPlay.Bind(wx.EVT_TOGGLEBUTTON, self.OnPlay)
        self.ButtonPrev.Bind(wx.EVT_BUTTON, self.OnPrev)
        self.ButtonNext.Bind(wx.EVT_BUTTON, self.OnNext)

        self.FilterBtn.Bind(wx.EVT_BUTTON, self.onFilter)
        self.RatingBtns.Bind(wx.EVT_RADIOBOX, self.onRate)

#-----------------------------------------------------------------------------------------------------------------------#
    # Scales the bitmap of the the buttons to a specific scale
    def scaleBitmap(self, bitmap):
        image = bitmap.ConvertToImage()
        image = image.Scale(25, 30, wx.IMAGE_QUALITY_HIGH)
        result = wx.Bitmap(image)
        return result

#-----------------------------------------------------------------------------------------------------------------------#
    # Clears playback, cover art panel and sets button to stopped.
    def clearPanel(self):
        self.Player.Stop()
        self.PlayerSlider.SetValue(0)
        self.disp.SetBitmap(wx.Bitmap(wx.Image(500, 500)))
        self.ButtonPlay.SetValue(False)

#-----------------------------------------------------------------------------------------------------------------------#
    # Get playlist box rows and pass to load.
    def loadSongFromListBox(self, e):
        row = e.GetEventObject().GetFocusedItem()
        self.loadSong(row)

#-----------------------------------------------------------------------------------------------------------------------#
    # Load song and pass more data to load and or store.
    def loadSong(self, row):
        self.clearRecommendationBox()
        d = []
        # Find which row is clicked in ListCtrl.
        cols = self.playlistBox.GetColumnCount()
        for col in range(cols-1):
            item = self.playlistBox.GetItem(itemIdx=row, col=col)
            d.append(item.GetText())

        # Assign artistName and SongTitle from ListCtrl.
        artistName = str(d[0])
        songTitle = str(d[1])

        # Find path of selected song.
        self.curs1.execute(
            '''SELECT path FROM playlist WHERE artist=? AND title=?''', (artistName, songTitle))
        path = ''.join(self.curs1.fetchone())

        # Get the amount of times the file has been played.
        self.curs1.execute(
            '''SELECT timesplayed FROM playlist WHERE path=?''', (path,))
        timesplayed = int(self.curs1.fetchone()[0])

        # Check if the path leads to a file.
        if os.path.isfile(path):

            # Load song onto player.
            self.Player.Load(path)
            self.PlayerSlider.SetRange(0, self.Player.Length())
            self.PlayerSlider.SetValue(0)
            self.Player.Play()
            self.setTimesPlayed(path, row)
            self.ButtonPlay.SetValue(True)

            # If the artist name is empty, try finding the name via AcoustID/LastFM combo.
            if artistName == '':
                self.getNamesLastFM(path)

            # Try to assign names from above function but handle exception if above function does not return any data.
            try:
                songTitle = self.song_name1
                artistName = self.artist_name1

            except:
                print("No name data from LastFM")
                print(songTitle + artistName)

            # If artist name is not empty then load a cover image and check for recommendations from Spotify.
            if artistName != '':
                self.makeCover(songTitle, artistName, path)

                # Check if song has already received recommendations and load them instead of searching again.
                found = False
                for recs in self.recommendations:
                    for x in recs:
                        if artistName == x[3]:
                            self.fillRecommendationBox(recs, artistName)
                            found = True
                            print(recs[3])
                            break
                if found is False and timesplayed < 1:
                    try:
                        self.songRecommendationByAlbumArtist(
                            songTitle, artistName)
                    except:
                        print("No recommendations by Album/Artist...")
                        print("Trying long query by Track/Artist...")
                        try:
                            self.songRecommendationByTrackArtist(
                                songTitle, artistName)
                        except:
                            print("No recommendations for current title..")
            # If the artist name is empty then skip the above and try loading only a cover image.
            else:
                self.makeCover(songTitle, artistName, path)

        # Search for file in paths below current if it has been moved.
        else:
            if os.name == 'nt':
                p = path.rsplit('\\', 1)
            else:
                p = path.rsplit('/', 1)

            dirr = p[0]
            songname = p[1]
            currpath = ""
            for root, dirs, files in os.walk(dirr):
                for file in files:
                    if file == songname:
                        currpath = os.path.join(root, file)
            if not currpath:
                wx.MessageBox("The file is missing.",
                              "ERROR", wx.ICON_ERROR | wx.OK)
                self.playlistBox.DeleteItem(self.playlistBox.GetFocusedItem())
                self.clearPanel()
                self.curs1.execute(
                    '''DELETE FROM playlist WHERE path=?''', (path,))
                self.conn1.commit()
                evt = wx.CommandEvent(
                    wx.wxEVT_COMMAND_BUTTON_CLICKED, self.ButtonNext.GetId())
                wx.PostEvent(self.ButtonNext, evt)
            # If the file is found, then update the location in the database.
            else:
                self.curs1.execute(
                    '''UPDATE playlist SET path=? WHERE path=?''', (currpath, path))
                self.conn1.commit()
                self.loadSong(row)

#-----------------------------------------------------------------------------------------------------------------------#
    # Sets the counter for each song based on the times they played the song
    def setTimesPlayed(self, path, row):
        # Finds the current value of the counter in the database
        self.curs1.execute(
            '''SELECT timesplayed FROM playlist WHERE path=?''', (path,))
        t = int(self.curs1.fetchone()[0])
        t += 1
        # Inputs the new incremented value of the counter
        self.curs1.execute(
            '''UPDATE playlist SET timesplayed=? WHERE path=?''', (t, path))
        self.conn1.commit()
        self.playlistBox.SetItem(row, 3, str(t))

#-----------------------------------------------------------------------------------------------------------------------#
    # Loads song that has been selected from the recommendation box.
    def loadSongFromRecommendationBox(self, e):
        d = []
        # Get selected row.
        row = e.GetEventObject().GetFocusedItem()
        count = self.recBox.GetItemCount()
        cols = self.recBox.GetColumnCount()
        for col in range(cols-1):
            item = self.recBox.GetItem(itemIdx=row, col=col)
            d.append(item.GetText())

        # Get names once again.
        artistName = str(d[0])
        songTitle = str(d[1])

        # If names match ones available in recommendation list of lists, then start song.
        for s in self.recommendations:
            for song in s:
                if song[0] == artistName and song[1] == songTitle:
                    self.Player.LoadURI(song[2])
                    self.Player.Play()
                    self.PlayerSlider.SetValue(0)
                    self.PlayerSlider.SetRange(0, 30000)
                    break

#-----------------------------------------------------------------------------------------------------------------------#
    # Loads all files from the selected folder
    def loadFolder(self, path):
        paths = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.lower().endswith(('.mp3', '.flac', '.wav', '.aac', 'ogg')):
                    paths.append(os.path.join(root, file))

        try:
            for x in paths:
                self.getMutagenTags(x)
            self.playlistBox.SetItemState(
                0, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED)
            self.playlistBox.Select(0, on=1)
        except:
            print("Mutagen error..")

#-----------------------------------------------------------------------------------------------------------------------#
    # Loads playlists
    def loadFiles(self, paths):
        try:
            for file in paths:
                self.getMutagenTags(file)
        except:
            print("Could not load multiple files..")

#-----------------------------------------------------------------------------------------------------------------------#
    # Loads data from playlist whilst formatting the query to a standart list instead of a tuple.
    def loadPlaylist(self):
        self.curs.row_factory = lambda cursor, row: row[0]
        self.curs.execute('''SELECT path FROM playlist''')
        data = self.curs.fetchall()
        return data

#-----------------------------------------------------------------------------------------------------------------------#
    # Fills the songs' data in the list
    def fillPlaylistBox(self, data):
        # Searches the database for rating if it exists
        list1 = (data[2], data[0], data[1])
        self.curs1.execute('''SELECT rating FROM rate WHERE artist=? AND title=?''', (str(
            list1[0]), str(list1[1])))
        rate = str(self.curs1.fetchone()[0])

        self.playlistBox.InsertItem(self.countListCttl, list1[0])
        self.playlistBox.SetItem(self.countListCttl, 1, str(list1[1]))
        self.playlistBox.SetItem(self.countListCttl, 2, str(list1[2]))
        self.playlistBox.SetItem(self.countListCttl, 3, str(0))
        if rate == "None":
            self.playlistBox.SetItem(self.countListCttl, 4, str(0))
        else:
            self.playlistBox.SetItem(self.countListCttl, 4, str(rate))
        self.countListCttl += 1

#-----------------------------------------------------------------------------------------------------------------------#
    # Fills the recomendation box with the currently recomended songs
    def fillRecommendationBox(self, data, artist_name):
        dur = '0:30'
        for x in data:
            if artist_name in x:
                list1 = (x[0], x[1], dur)
                self.recBox.InsertItem(0, str(list1[0]))
                self.recBox.SetItem(0, 1, str(list1[1]))
                self.recBox.SetItem(0, 2, str(list1[2]))

#-----------------------------------------------------------------------------------------------------------------------#
    # Clear the recomendation box from its data
    def clearRecommendationBox(self):
        self.recBox.DeleteAllItems()

#-----------------------------------------------------------------------------------------------------------------------#
    # Create table for the currently running playlist.
    def createTableRunning(self):
        self.curs1.execute('''CREATE TABLE IF NOT EXISTS playlist
                            (title VARCHAR(255) UNIQUE,
                            duration VARCHAR(255),
                            artist VARCHAR(255),
                            year VARCHAR(255),
                            path VARCHAR(255),
                            timesplayed VARCHAR(255))''')
        self.curs1.execute('DELETE FROM playlist;')
        self.conn1.commit()

#-----------------------------------------------------------------------------------------------------------------------#
    # create the table of ratingdb
    def createTableRating(self):
        self.curs1.execute('''CREATE TABLE IF NOT EXISTS rate
                            (title VARCHAR(255) UNIQUE,
                            artist VARCHAR(255),
                            rating VARCHAR(255))''')
        self.conn1.commit()

#-----------------------------------------------------------------------------------------------------------------------#
    # Establish connection with currentpl
    def establishConnectionRun(self):
        self.conn1 = None
        try:
            self.conn1 = sqlite3.connect(currentpl)
        except sqlite3.Error as e:
            print(e)
            print("Unable to establish connection to database...\n")

        self.curs1 = self.conn1.cursor()
        self.createTableRunning()
        self.createTableRating()

#-----------------------------------------------------------------------------------------------------------------------#
    # Establish connection with saved playlist's database
    def establishConnectionPl(self, path):
        self.conn = None
        try:
            self.connn = sqlite3.connect(path)
        except sqlite3.Error as e:
            print(e)
            print("Unable to establish connection to database...\n")

        self.curs = self.conn1.cursor()

#-----------------------------------------------------------------------------------------------------------------------#
    # Insert data into ratingdb
    def playlistrate(self, data):
        self.curs1.execute('''REPLACE INTO rate(title, artist, rating)
                    VALUES(?, ?, (select rating from rate where title=? and artist=?))''', (data[0], data[2], data[0], data[2]))
        self.conn1.commit()

#-----------------------------------------------------------------------------------------------------------------------#
    # Add new songs to database.
    def playlistd(self, data):
        self.curs1.execute('''REPLACE INTO playlist(title,duration,artist,year,path,timesplayed)
                    VALUES(?,?,?,?,?,?)''', (data[0], data[1], data[2], data[3], data[4], 0))
        self.conn1.commit()

#-----------------------------------------------------------------------------------------------------------------------#
    # Operates with ID3 tags
    def getMutagenTags(self, path):
        data = []
        # Creates the MutaFile
        try:
            song = MutaFile(path)
            self.d = int(song.info.length)
        except:
            # Calculates the song lenght if the song is in .wave format
            with contextlib.closing(wave.open(path, 'r')) as file:
                frames = file.getnframes()
                rate = file.getframerate()
                self.d = frames / float(rate)
        title = 'n/a'
        artist = ''
        # Backup in case there are no ID3 tags and the API can't find new ones
        backup_name = os.path.split(path)
        backup_name = backup_name[-1]
        backup_name = backup_name.split('.')
        backup_name = str(backup_name[0])

        title = backup_name

        try:
            audio = ID3(path)
            self.artist_name = audio['TPE1'].text[0]
            self.song_name = audio['TIT2'].text[0]
            self.artist_name = re.split(',|\(|\)|\?', self.artist_name)
            self.artist_name = self.artist_name[0]
            self.song_name = re.split(',|\(|\)|\?', self.song_name)
            self.song_name = self.song_name[0]
            song_year = str(audio['TDRC'].text[0])
        except:
            self.artist_name = artist
            self.song_name = title
            song_year = ''

        # Insert song data in list for inserting in database of currently playing songs.
        minutes = int(self.d // 60)
        seconds = int(self.d % 60)
        duration = str(minutes) + ":" + str(seconds)

        data.append(self.song_name)
        data.append(duration)
        data.append(self.artist_name)
        data.append(song_year)
        data.append(path)

        check = False
        # If the song is already in the list it is not inserted again
        if self.playlistBox.GetItemCount() > 0:
            count = self.playlistBox.GetItemCount()
            cols = self.playlistBox.GetColumnCount()
            for row in range(count):
                temp = []
                for col in range(cols-2):
                    item = self.playlistBox.GetItem(itemIdx=row, col=col)
                    temp.append(item.GetText())
                if temp[0] == self.artist_name and temp[1] == self.song_name:
                    check = True
                    break

        if check == False:
            self.playlistrate(data)
            self.playlistd(data)
            self.fillPlaylistBox(data)

#-----------------------------------------------------------------------------------------------------------------------#
    # Get Song name and Artist name if not available in ID3.
    def getNamesLastFM(self, path):

        # Use acoustid API to get song data if ID3 tags are not available.
        fing = fingerprint_file(path, force_fpcalc=True)
        fing = fing[1]
        fing = str(fing)
        fing = fing[2:-1]
        url = 'https://api.acoustid.org/v2/lookup?client='
        url += akey
        url += '&meta=recordings+releasegroups+compress&duration='
        url += str(self.d)
        url += '&fingerprint='
        url += fing
        try:
            text = urllib.request.urlopen(url)
            parsed = json.loads(text.read())
            names = list(acoustid.parse_lookup_result(parsed))
            for x in names:
                if None not in x:
                    names = x
                    title = names[-2]
                    artist = names[-1]
                    # Check if any feat. artists names in original name.
                    if ';' in artist:
                        artist = artist.split(';')
                        artist = artist[0]
                    if ',' in artist:
                        artist = artist.split(',')
                        artist = artist[0]
                    break
            self.artist_name1 = artist
            self.song_name1 = title
        except:
            print("No name data during search...")

#-----------------------------------------------------------------------------------------------------------------------#
    # LastFM API call to get album cover.
    def makeCover(self, track_name, artist_name, path):
        # Set a blank bitmap on the static bitmap.
        self.disp.SetBitmap(wx.Bitmap(wx.Image(500, 500)))
        url = 'http://ws.audioscrobbler.com/2.0/?method=track.getInfo&format=json&api_key='
        url += lkey
        url += '&artist=' + urllib.parse.quote(artist_name) + \
            '&track=' + urllib.parse.quote(track_name)
        try:
            link = urllib.request.urlopen(url)
            parsed = json.load(link)

        except:
            print("Failed to load cover.")

            try:
                # First try loading an image from ID3
                tags = ID3(path)
                filename = tags.get("APIC:").data
                # Convert Bytes data to PIL image.
                image = Image.open(BytesIO(filename))
                self.displayimage(image)
            except:
                try:
                    imagelinks = parsed['track']['album']['image']
                    imagelink = imagelinks[3]['#text']
                    filename = urllib.request.urlopen(imagelink)
                    image = Image.open(filename)
                    self.displayimage(image)
                except:
                    print("Failed to load cover.")

#-----------------------------------------------------------------------------------------------------------------------#
    # Load conver PIL image to wx.Image file and load it to a static bitmap.
    def displayimage(self, image):
        self.width, self.height = image.size
        image.thumbnail((500, 500))
        self.PilImageToWxImage(image)

#-----------------------------------------------------------------------------------------------------------------------#
    # Conver PIL image to wx.Image whilst checking if the image has alpha and load it to a static Bitmap.
    def PilImageToWxImage(self, img):

        myWxImage = wx.Image(img.size[0], img.size[1])

        dataRGB = img.convert(
            'RGB').tobytes()
        myWxImage.SetData(dataRGB)
        if myWxImage.HasAlpha():
            dataRGBA = img.tobytes()[3::4]
            myWxImage.SetAlphaData(dataRGBA)
        self.disp.SetBitmap(wx.Bitmap(myWxImage))

#-----------------------------------------------------------------------------------------------------------------------#
    # API call to get song recommendations by Album name and Artist name.
    def getSongRecommendationByAlbumArtist(self, track_name, artist_name):
        # Use LastFM to get the album name.
        print(artist_name + ' -- ' + track_name)
        # Get album name for reference from LastFM API.
        album_name = ''
        uurl = 'http://ws.audioscrobbler.com/2.0/?method=track.getInfo&limit=10&format=json&api_key='
        uurl += lkey
        uurl += '&artist=' + urllib.parse.quote(artist_name) + \
            '&track=' + urllib.parse.quote(track_name)

        uurlink = urllib.request.urlopen(uurl)
        pparsed = json.load(uurlink)
        album_name = pparsed['track']['album']['title']

        recommendations = []
        sp = spotipy.Spotify(
            client_credentials_manager=SpotifyClientCredentials())
        off = 0
        found = False
        # Recursively call on spotify API to find artist url.
        try:
            while (found is False and off < 100):
                # Search for album in spotify.
                album_search = sp.search(
                    q='album:'+album_name+' '+'artist:'+artist_name, limit=50, type='album', offset=off)

                for album in album_search['albums']['items']:
                    album_name_sp = album['name']
                    if artist_name.lower() == str(album['artists'][0]['name']).lower():

                        self.artist_url = album['artists'][0]['id']
                        sp_artist_name = album['artists'][0]['name']
                        found = True
                        break
                off += 50
        except:
            print("Error during search.")

        # Pass artist url as list of one to find recommendations.
        artist_seed = []
        artist_seed.append(self.artist_url)
        rec = sp.recommendations(seed_artists=artist_seed, limit=20)

        # Raise exception if no recommendations are found.
        if len(rec['tracks']) == 0:
            raise Exception

        # Find all recommended songs that have a preview URL and store them in a list with the parent artist URL.
        for track in rec['tracks']:
            if track['preview_url'] is not None:

                preview_url = track['preview_url']
                title = track['name # Raise exception if no recommendations are found.']

                art_name = track['album']['artists'][0]['name']
                data = [art_name, title, preview_url, artist_name]

                # Pass list to list in order to check later if information has already been gathered.
                recommendations.append(data)
        self.recommendations.append(recommendations)
        self.fillRecommendationBox(recommendations, artist_name)

#-----------------------------------------------------------------------------------------------------------------------#
    # API call to get song recommendations by Song name and Artist name.
    def songRecommendationByTrackArtist(self, track_name, artist_name):
        artist_url = ''
        recommendations = []
        sp = spotipy.Spotify(
            client_credentials_manager=SpotifyClientCredentials())

        found = False
        off = 0
        # Recursively call on spotify API to find artist url.
        try:
            while (found is False or off < 150):
                track_search = sp.search(
                    q='track:'+track_name+' '+'artist:'+artist_name, limit=50, type='track', offset=off)

                for track in track_search['tracks']['items']:
                    artist_url = track['artists'][0]['id']
                    found = True
                    # print(str(artist_url))
                    break

                off += 50
        except:
            print("Error during Spotify search.")

        # Pass artist url as list of one to find recommendations.
        artist_seed = []
        artist_seed.append(artist_url)
        try:
            rec = sp.recommendations(seed_artists=artist_seed, limit=20)
        except:
            print("Error during search")

        # Raise exception if no recommendations are found.
        if len(rec['tracks']) == 0:
            raise Exception("No recommendations")

        # Find all recommended songs that have a preview URL and store them in a list with the parent artist URL.
        for track in rec['tracks']:
            if track['preview_url'] is not None:

                preview_url = track['preview_url']
                title = track['name']
                art_name = track['album']['artists'][0]['name']
                data = [art_name, title, preview_url, artist_name]

                # Pass list to list in order to check later if information has already been gathered.
                recommendations.append(data)
        self.recommendations.append(recommendations)
        self.fillRecommendationBox(recommendations, artist_name)

#-----------------------------------------------------------------------------------------------------------------------#
    # On next button select next song to load and play.
    def OnNext(self, event):
        current = self.playlistBox.GetFocusedItem()
        if current < self.playlistBox.GetItemCount()-1:
            self.playlistBox.SetItemState(
                current+1, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED)
            self.playlistBox.Select(current, on=0)
            self.playlistBox.Select(current+1, on=1)
        else:
            self.playlistBox.Select(current, on=0)
            self.playlistBox.Select(current, on=1)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    # On previous button select previous song to load and play.
    def OnPrev(self, event):
        current = self.playlistBox.GetFocusedItem()
        if current > self.playlistBox.GetTopItem():
            self.playlistBox.SetItemState(
                current-1, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED)
            self.playlistBox.Select(current, on=0)
            self.playlistBox.Select(current-1, on=1)
        else:
            self.playlistBox.Select(current, on=0)
            self.playlistBox.Select(current, on=1)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    # Pause player.
    def OnPause(self):
        self.Player.Pause()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    # Play song.
    def OnPlay(self, event):
        if not event.GetEventObject().GetValue():
            self.OnPause()
            return

        # Error if no song loaded.
        if not self.Player.Play():
            self.ButtonPlay.SetValue(False)
            wx.MessageBox("A file must be selected.",
                          "ERROR", wx.ICON_ERROR | wx.OK)

        # Set player slider to beginning if the song starts.
        else:
            self.PlayerSlider.SetRange(0, self.Player.Length())

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    # Option to grab slider and seek song.
    def OnSeek(self, event):
        value = self.PlayerSlider.GetValue()
        self.Player.Seek(value)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    # Handle volume adjustments.
    def onVolume(self, event):
        self.currentVolume = self.volumeCtrl.GetValue()
        self.Player.SetVolume(self.currentVolume/100)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    # Handle filter button to filter songs by attributes.
    def onFilter(self, event):
        txt = self.enterPref.GetValue()
        idxsel = self.combo.GetCurrentSelection()
        sel = self.combo.GetString(idxsel)
        if sel == "Artist":
            rows = self.playlistBox.GetItemCount()
            row = 0
            while row < rows:
                title = self.playlistBox.GetItem(itemIdx=row, col=1)
                item = self.playlistBox.GetItem(itemIdx=row, col=0)
                if item.GetText().lower() != txt.lower():
                    self.playlistBox.DeleteItem(row)
                    self.curs.execute(
                        '''DELETE FROM playlist WHERE artist=? AND title=?''', (item.GetText(), title.GetText()))
                    self.conn1.commit()
                    rows -= 1
                    row -= 1
                row += 1

        elif sel == "Title":
            rows = self.playlistBox.GetItemCount()
            row = 0
            while row < rows:
                artist = self.playlistBox.GetItem(itemIdx=row, col=0)
                item = self.playlistBox.GetItem(itemIdx=row, col=1)
                if item.GetText().lower() != txt.lower():
                    self.playlistBox.DeleteItem(row)
                    self.curs1.execute(
                        '''DELETE FROM playlist WHERE artist=? AND title=?''', (artist.GetText(), item.GetText()))
                    self.conn1.commit()
                    rows -= 1
                    row -= 1
                row += 1

        self.clearPanel()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    # Handle song rating *.db. Update values when rating songs.
    def onRate(self, event):
        cur = self.playlistBox.GetFocusedItem()
        artist = self.playlistBox.GetItem(itemIdx=cur, col=0)
        title = self.playlistBox.GetItem(itemIdx=cur, col=1)
        self.playlistBox.SetItem(cur, 4, event.GetString())
        rate = event.GetString()
        self.curs1.execute('''UPDATE rate SET rating=? WHERE artist=? AND title=?''',
                           (rate, artist.GetText(), title.GetText()))
        self.conn1.commit()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
    # Timer that follows song playback constantly. If repeat is pressed it selects the same song to call self.loadsong().
    def onTimer(self, event):
        value = self.Player.Tell()
        self.PlayerSlider.SetValue(value)
        if not self.ButtonRepeat.GetValue():
            if value > self.Player.Length():
                current = self.playlistBox.GetFocusedItem()
                if current < self.playlistBox.GetItemCount()-1:
                    self.playlistBox.SetItemState(
                        current+1, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED)
                    self.playlistBox.Select(current, on=0)
                    self.playlistBox.Select(current+1, on=1)
        if self.ButtonRepeat.GetValue():
            if value >= self.Player.Length():
                current = self.playlistBox.GetFocusedItem()
                self.playlistBox.SetItemState(
                    current, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED)
                self.playlistBox.Select(current, on=0)
                self.playlistBox.SetItemState(
                    current, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED)
                self.playlistBox.Select(current, on=1)
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#


app = wx.App()
frame = Ultra(None, -1)
frame.Show()
app.MainLoop()
