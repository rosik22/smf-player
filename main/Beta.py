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
from spotipy.oauth2 import SpotifyClientCredentials
from mutagen.id3 import ID3
from mutagen import File as MutaFile
from spotipy.oauth2 import SpotifyClientCredentials
from acoustid import fingerprint_file
from xml.dom.minidom import parseString
from PIL import Image
from functools import partial
from io import BytesIO

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
            None, title="Scope", style=no_resize, size=(600, 850), pos=(0, 0))

        self.establishConnection()

        self.SetBackgroundColour("Black")

        # Playback panel
        self.panel = wx.Panel(self, size=(600, 100))
        self.panel.SetBackgroundColour("Black")

        # Panel for album cover
        self.display = wx.Panel(self, size=(200, 200))
        self.display.SetBackgroundColour("Black")
        self.disp = wx.StaticBitmap(
            self.display, size=(200, 200), pos=(200, 0))
        self.artist_name = ''
        self.song_name = ''

        # Panel for playlist listbox and filter options.
        self.plbox = wx.Panel(self, size=(600, 550))
        self.playlistBox = wx.ListCtrl(self.plbox, size=(
            550, 425), pos=(25, 25), style=wx.LC_REPORT)
        self.playlistBox.AppendColumn("Artist", width=200)
        self.playlistBox.AppendColumn("Title", width=200)
        self.playlistBox.AppendColumn("Duration", width=100)
        self.playlistBox.Bind(wx.EVT_LIST_ITEM_SELECTED,
                              self.loadSongFromListBox)
        self.plbox.SetBackgroundColour("White")

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer)
        self.timer.Start(100)

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
    def menuhandler(self, num, event):
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
                    self.makeCover(
                        self.song_name, self.artist_name, pathname)
                    self.PlayerSlider.SetRange(0, self.Player.Length())
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
                    self.PlayerSlider.SetRange(0, self.Player.Length())
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

        self.PlayerSlider = wx.Slider(
            self.panel, style=wx.SL_HORIZONTAL, size=(400, -1), pos=(100, 10))
        self.Bind(wx.EVT_SLIDER, self.OnSeek, self.PlayerSlider)

        # Sizer for different panels.
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.display, flag=wx.EXPAND | wx.ALL)
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

        self.curs.execute(
            '''SELECT path FROM playlist WHERE artist=? AND title=? ''', (artistName, songTitle))
        path = ''.join(self.curs.fetchone())

        self.Player.Load(path)
        self.PlayerSlider.SetRange(0, self.Player.Length())
        self.makeCover(songTitle, artistName, path)
        self.Player.Play()
        self.ButtonPlay.SetValue(True)

#-----------------------------------------------------------------------------------------------------------------------#
    def scaleBitmap(self, bitmap):
        image = bitmap.ConvertToImage()
        image = image.Scale(25, 30, wx.IMAGE_QUALITY_HIGH)
        result = wx.Bitmap(image)
        return result

#-----------------------------------------------------------------------------------------------------------------------#
    def Buttons(self):
        picPlayBtn = wx.Bitmap("play-button.png", wx.BITMAP_TYPE_ANY)
        picPlayBtn = self.scaleBitmap(picPlayBtn)

        picPrevBtn = wx.Bitmap("previous-song-button.png", wx.BITMAP_TYPE_ANY)
        picPrevBtn = self.scaleBitmap(picPrevBtn)

        picNextBtn = wx.Bitmap("next-song-button.png", wx.BITMAP_TYPE_ANY)
        picNextBtn = self.scaleBitmap(picNextBtn)

        self.ButtonPlay = wx.BitmapToggleButton(
            self.panel, label=picPlayBtn, pos=(275, 40))

        self.ButtonPrev = wx.BitmapToggleButton(
            self.panel, label=picPrevBtn, pos=(210, 40))

        self.ButtonBtn = wx.BitmapToggleButton(
            self.panel, label=picNextBtn, pos=(340, 40))

        self.ButtonPlay.Bind(wx.EVT_TOGGLEBUTTON, self.OnPlay)

#-----------------------------------------------------------------------------------------------------------------------#
    def getMutagenTags(self, path):
        data = []
        song = MutaFile(path)
        d = int(song.info.length)

        # Use acoustid API to get song data if ID3 tags are not available.
        fing = fingerprint_file(path, force_fpcalc=True)
        fing = fing[1]
        fing = str(fing)
        fing = fing[2:-1]
        url = 'https://api.acoustid.org/v2/lookup?client=Bklmy2zJQL&meta=recordings+releasegroups+compress&duration='
        url += str(d)
        url += '&fingerprint='
        url += fing
        text = urllib.request.urlopen(url)
        parsed = json.loads(text.read())
        names = list(acoustid.parse_lookup_result(parsed))
        for x in names:
            if None not in x:
                names = x
                title = names[-2]
                artist = names[-1]
                # Call for a recommendation based on LastFM data for song.
                self.getSongRecommendation(title, artist)
                break
            else:
                title = ''
                artist = ''
        # print(names)

        # Check if file has ID3 tags. If not, use the LastFM API for naming.
        try:
            audio = ID3(path)
            self.id3tags = audio
            self.artist_name = audio['TPE1'].text[0]
            self.song_name = audio['TIT2'].text[0]
            song_year = str(audio['TDRC'].text[0])
            self.getSongRecommendation(self.song_name, self.artist_name)
        except:
            self.artist_name = artist
            self.song_name = title
            song_year = ''

        # Insert song data in list for inserting in database of currently playing songs.
        minutes = d // 60
        seconds = d % 60
        duration = str(minutes) + ":" + str(seconds)

        data.append(self.song_name)
        data.append(duration)
        data.append(self.artist_name)
        data.append(song_year)
        data.append(path)

        self.playlistd(data)
        self.fillPlaylistBox(data)

#-----------------------------------------------------------------------------------------------------------------------#
    def fillPlaylistBox(self, data):
        list1 = (data[2], data[0], data[1])
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
                    VALUES(?,?,?,?,?)''', (data[0], data[1], data[2], data[3], data[4]))
        self.conn.commit()

#-----------------------------------------------------------------------------------------------------------------------#
    def makeCover(self, track_name, artist_name, path):
        url = 'http://ws.audioscrobbler.com/2.0/?method=track.getInfo&format=json&api_key=5240ab3b0de951619cb54049244b47b5&artist='
        url += urllib.parse.quote(artist_name) + \
            '&track=' + urllib.parse.quote(track_name)
        # print(url)
        link = urllib.request.urlopen(url)
        parsed = json.load(link)
        try:
            tags = ID3(path)
            filename = tags.get("APIC:").data
            self.pilimage = Image.open(BytesIO(filename))
        except:
            try:
                imagelinks = parsed['track']['album']['image']
                imagelink = imagelinks[3]['#text']
                filename = urllib.request.urlopen(imagelink)
                self.pilimage = Image.open(filename)
            except:
                print("No album cover could be loaded for the given song...")
        self.displayimage(filename)

#-----------------------------------------------------------------------------------------------------------------------#
    def displayimage(self, path):
        self.width, self.height = self.pilimage.size
        self.pilimage.thumbnail((200, 200))
        self.PilImageToWxImage(self.pilimage)

#-----------------------------------------------------------------------------------------------------------------------#
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
    def getSongRecommendation(self, track_name, artist_name):
        """ url = 'http://ws.audioscrobbler.com/2.0/?method=track.getsimilar&limit=10&api_key=5240ab3b0de951619cb54049244b47b5&format=json&artist='
        url += urllib.parse.quote(artist_name) + \
            '&track=' + urllib.parse.quote(track_name)
        print(url)
        link = urllib.request.urlopen(url)
        parsed = json.load(link)
        for track in parsed['similartracks']['track']:
            print(track['name']) """

        sp = spotipy.Spotify(
            client_credentials_manager=SpotifyClientCredentials())

        results = sp.search(q=artist_name, limit=10, type='artist')
        artist_url = results['artists']['items'][0]['external_urls']['spotify']
        artist_url = str(artist_url)
        artist_url = artist_url.split('artist/', 1)
        artist_url = artist_url[1]
        artist_seed = []
        artist_seed.append(artist_url)
        rec = sp.recommendations(seed_artists=artist_seed, limit=10)
        for track in rec['tracks']:
            if track['preview_url'] is not None:
                preview_url = track['preview_url']
                title = track['name']
            print(str(track['preview_url']) + ' -- ' + track['name'])
            track_name = track['name']
            art_name = track['album']['artists'][0]['name']
        


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
        value = self.PlayerSlider.GetValue()
        self.Player.Seek(value)

    def onTimer(self, event):
        value = self.Player.Tell()
        self.PlayerSlider.SetValue(value)


app = wx.App()
frame = Scope(None, -1)
frame.Show()
app.MainLoop()
