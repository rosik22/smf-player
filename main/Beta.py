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
recommendation_data = 'rec.db'


class Scope(wx.Frame):
    def __init__(self, parent, id):

        no_resize = wx.DEFAULT_FRAME_STYLE & ~ (wx.RESIZE_BORDER |
                                                wx.MAXIMIZE_BOX)
        super().__init__(
            None, title="Scope", style=no_resize, size=(600, 920), pos=(0, 0))

        self.establishConnectionRun()

        self.SetBackgroundColour("Black")
        self.countListCttl = 0
        self.countAddToPlaylist = 0
       # self.allPaths = {}

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
        self.plbox = wx.Panel(self, size=(400, 350))
        self.playlistBox = wx.ListCtrl(self.plbox, size=(
            550, 310), pos=(25, 10), style=wx.LC_REPORT)
        self.playlistBox.AppendColumn("Artist", width=150)
        self.playlistBox.AppendColumn("Title", width=150)
        self.playlistBox.AppendColumn("Duration", width=150)
        self.playlistBox.AppendColumn("Times played", width=100)
        self.playlistBox.Bind(wx.EVT_LIST_ITEM_SELECTED,
                              self.loadSongFromListBox)

        self.plbox.SetBackgroundColour("Gray")

        # Panel for song recommendations.
        self.rec = wx.Panel(self, size=(300, 250))
        self.recBox = wx.ListCtrl(self.rec, size=(
            550, 200), pos=(25, 0), style=wx.LC_REPORT)
        self.recBox.AppendColumn("Artist", width=200)
        self.recBox.AppendColumn("Title", width=200)
        self.recBox.AppendColumn("Duration", width=100)
        self.recommendations = []
        self.recBox.Bind(wx.EVT_LIST_ITEM_SELECTED,
                         self.loadSongFromRecommendationBox)
        self.rec.SetBackgroundColour("Gray")
        self.recommendations = []

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
        self.Player.SetVolume(1.0)
        self.Destroy()

#-----------------------------------------------------------------------------------------------------------------------#
    # Menubar settings.
    def createMenu(self):
        menubar = wx.MenuBar()
        filemenu = wx.Menu()
        openf = filemenu.Append(-1, '&Open folder')
        open1 = filemenu.Append(-1, '&Open')
        add = filemenu.Append(-1, '&Add to playlist')
        exit2 = filemenu.Append(-1, '&Exit')
        menubar.Append(filemenu, '&File')
        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU, partial(self.menuhandler, 1), openf)
        self.Bind(wx.EVT_MENU, partial(self.menuhandler, 2), open1)
        self.Bind(wx.EVT_MENU, partial(self.menuhandler, 3), add)
        self.Bind(wx.EVT_MENU, partial(self.menuhandler, 4), exit2)

#-----------------------------------------------------------------------------------------------------------------------#
    # Function to handle menubar options.
    def menuhandler(self, num, event):
        id = event.GetId()
        if num == 1:
            with wx.DirDialog(self.panel, "Open Music Dir", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as directory:

                if directory.ShowModal() == wx.ID_CANCEL:
                    return

                pathname = directory.GetPath()

                try:
                    self.loadFolder(pathname)
                except:
                    print("Error during loading the path and/or files within...")

        if num == 2:
            with wx.FileDialog(self.panel, "Open Music file", wildcard="Music files (*.mp3,*.wav,*.aac,*.ogg,*.flac)|*.mp3;*.wav;*.aac;*.ogg;*.flac",
                               style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file:

                if file.ShowModal() == wx.ID_CANCEL:
                    return

                pathname = file.GetPath()
                self.countListCttl = 0
                
                try:
                    self.curs.execute('DELETE FROM playlist;')
                    self.conn.commit()
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

        elif num == 3:
            with wx.FileDialog(self.panel, "Open Image file", wildcard="Music files (*.mp3,*.wav,*.aac,*.ogg,*.flac)|*.mp3;*.wav;*.aac;*.ogg;*.flac",
                               style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file:

                if file.ShowModal() == wx.ID_CANCEL:
                    return

                pathname = file.GetPath()

                try:
                    if self.Player.Length() == -1:
                        self.Player.Load(pathname)
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

        elif num == 4:
            self.Close()

#-----------------------------------------------------------------------------------------------------------------------#
    # Sets the layout
    def createLayout(self):
        try:
            self.Player = wx.media.MediaCtrl(self, style=wx.SIMPLE_BORDER)
        except NotImplementedError:
            self.Destroy()
            raise

        self.PlayerSlider = wx.Slider(self.panel, style=wx.SL_HORIZONTAL, size=(400,-1), pos=(100,10))
        self.PlayerSlider.Bind(wx.EVT_SLIDER, self.OnSeek, self.PlayerSlider)

        # Slider for volume
        self.currentVolume = 100
        self.volumeCtrl = wx.Slider(self.panel, style=wx.SL_HORIZONTAL, size=(100,-1), pos=(400,40))
        self.volumeCtrl.SetRange(0, 100)
        self.volumeCtrl.SetValue(100)
        self.Player.SetVolume(1.0)
        self.volumeCtrl.Bind(wx.EVT_SLIDER, self.onVolume, self.volumeCtrl)

        # Sizer for different panels.
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.display, flag=wx.EXPAND | wx.ALL)
        sizer.Add(self.panel, flag=wx.EXPAND | wx.ALL)
        sizer.Add(self.plbox, flag=wx.EXPAND | wx.ALL)
        sizer.Add(self.rec, flag=wx.EXPAND | wx.ALL)
        self.SetSizer(sizer)

#-----------------------------------------------------------------------------------------------------------------------#
    def loadSongFromListBox(self, e):
        row = e.GetEventObject().GetFocusedItem()
        self.loadSong(row)

#-----------------------------------------------------------------------------------------------------------------------#
    def loadSong(self, row):
        self.clearRecommendationBox()
        d = []
        cols = self.playlistBox.GetColumnCount()
        for col in range(cols-1):
            item = self.playlistBox.GetItem(itemIdx=row, col=col)
            d.append(item.GetText())

        artistName = str(d[0])
        songTitle = str(d[1])

        self.curs.execute(
            '''SELECT path FROM playlist WHERE artist=? AND title=?''', (artistName, songTitle))
        path = ''.join(self.curs.fetchone())

        self.curs.execute(
            '''SELECT timesplayed FROM playlist WHERE path=?''', (path,))
        timesplayed = int(self.curs.fetchone()[0])

        self.Player.Load(path)
        self.PlayerSlider.SetRange(0, self.Player.Length())
        self.Player.Play()
        self.setTimesPlayed(path, row)
        self.ButtonPlay.SetValue(True)
        self.makeCover(songTitle, artistName, path)
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
                    self.getSongRecommendationByAlbumArtist(songTitle, artistName)
                except:
                    print("No recommendations by Album/Artist...")
                    print("Trying long query by Track/Artist...")
                    try:
                        self.songRecommendationByTrackArtist(songTitle, artistName)
                    except:
                        print("No recommendations for current title..")
#-----------------------------------------------------------------------------------------------------------------------#

    def loadSongFromRecommendationBox(self, e):
        d = []
        row = e.GetEventObject().GetFocusedItem()
        count = self.recBox.GetItemCount()
        cols = self.recBox.GetColumnCount()
        for col in range(cols-1):
            item = self.recBox.GetItem(itemIdx=row, col=col)
            d.append(item.GetText())

        artistName = str(d[0])
        songTitle = str(d[1])
        for s in self.recommendations:
            for song in s:
                if song[0] == artistName and song[1] == songTitle:
                    self.Player.LoadURI(song[2])
                    self.Player.Play()
                    break

#-----------------------------------------------------------------------------------------------------------------------#
    def setTimesPlayed(self, path, row):
        self.curs.execute(
            '''SELECT timesplayed FROM playlist WHERE path=?''', (path,))
        t = int(self.curs.fetchone()[0])
        t += 1
        self.curs.execute(
            '''UPDATE playlist SET timesplayed=? WHERE path=?''', (t, path))
        self.conn.commit()
        self.playlistBox.SetItem(row, 3, str(t))

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

        self.ButtonPrev = wx.BitmapButton(
            self.panel, bitmap=picPrevBtn, pos=(210, 40))

        self.ButtonNext = wx.BitmapButton(
            self.panel, bitmap=picNextBtn, pos=(340, 40))

        self.ButtonPlay.Bind(wx.EVT_TOGGLEBUTTON, self.OnPlay)
        self.ButtonPrev.Bind(wx.EVT_BUTTON, self.OnPrev)
        self.ButtonNext.Bind(wx.EVT_BUTTON, self.OnNext)

#-----------------------------------------------------------------------------------------------------------------------#
    def getMutagenTags(self, path):
        data = []
        try:
            song = MutaFile(path)
            d = int(song.info.length)
        except:
            with contextlib.closing(wave.open(path, 'r')) as file:
                frames = file.getnframes()
                rate = file.getframerate()
                d = frames / float(rate)
        title = 'n/a'
        artist = 'n/a'
        backup_name = os.path.split(path)
        backup_name = backup_name[-1]
        backup_name = backup_name.split('.')
        backup_name = str(backup_name[0])

        # print(backup_name)
        title = backup_name

        # Use acoustid API to get song data if ID3 tags are not available.
        fing = fingerprint_file(path, force_fpcalc=True)
        fing = fing[1]
        fing = str(fing)
        fing = fing[2:-1]
        url = 'https://api.acoustid.org/v2/lookup?client=Bklmy2zJQL&meta=recordings+releasegroups+compress&duration='
        url += str(d)
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
                    if ';' in artist:
                        artist = artist.split(';')
                        artist = artist[0]
                    break
        except:
            print("No name data...")
        # Check if file has ID3 tags. If not, use the LastFM API for naming.
        try:
            audio = ID3(path)
            self.artist_name = audio['TPE1'].text[0]
            self.song_name = audio['TIT2'].text[0]
            song_year = str(audio['TDRC'].text[0])
        except:
            self.artist_name = artist
            self.song_name = title
            song_year = ''

        # Insert song data in list for inserting in database of currently playing songs.
        minutes = int(d // 60)
        seconds = int(d % 60)
        duration = str(minutes) + ":" + str(seconds)

        data.append(self.song_name)
        data.append(duration)
        data.append(self.artist_name)
        data.append(song_year)
        data.append(path)

        #self.allPaths[self.artist_name] = {}
        #self.allPaths[self.artist_name][self.song_name]

        check = False
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
            self.playlistd(data)
            self.fillPlaylistBox(data)

#-----------------------------------------------------------------------------------------------------------------------#
    def loadFolder(self, path):
        paths = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.lower().endswith(('.mp3', '.flac', '.wav', '.aac', 'ogg')):
                    paths.append(os.path.join(root, file))

        for x in paths:
            self.getMutagenTags(x)

#-----------------------------------------------------------------------------------------------------------------------#
    def fillPlaylistBox(self, data):
        list1 = (data[2], data[0], data[1])
        self.playlistBox.InsertItem(self.countListCttl, list1[0])
        self.playlistBox.SetItem(self.countListCttl, 1, str(list1[1]))
        self.playlistBox.SetItem(self.countListCttl, 2, str(list1[2]))
        self.playlistBox.SetItem(self.countListCttl, 3, str(0))
        self.countListCttl += 1

#-----------------------------------------------------------------------------------------------------------------------#
    def fillRecommendationBox(self, data, artist_name):
        dur = '0:30'
        for x in data:
            if artist_name in x:
                list1 = (x[0], x[1], dur)
                self.recBox.InsertItem(0, str(list1[0]))
                self.recBox.SetItem(0, 1, str(list1[1]))
                self.recBox.SetItem(0, 2, str(list1[2]))

#-----------------------------------------------------------------------------------------------------------------------#
    def clearRecommendationBox(self):
        self.recBox.DeleteAllItems()

#-----------------------------------------------------------------------------------------------------------------------#
    def establishConnectionRun(self):
        self.conn = None
        try:
            self.conn = sqlite3.connect(currentpl)
        except sqlite3.Error as e:
            print(e)
            print("Unable to establish connection to database...\n")

        self.curs = self.conn.cursor()
        self.createTableRunning()

#-----------------------------------------------------------------------------------------------------------------------#
    def createTableRunning(self):
        self.curs.execute('''CREATE TABLE IF NOT EXISTS playlist
                            (title VARCHAR(255) UNIQUE,
                            duration VARCHAR(255),
                            artist VARCHAR(255),
                            year VARCHAR(255),
                            path VARCHAR(255),
                            timesplayed VARCHAR(255))''')
        self.curs.execute('DELETE FROM playlist;')
        self.conn.commit()

#-----------------------------------------------------------------------------------------------------------------------#
    def playlistd(self, data):
        self.curs.execute('''REPLACE INTO playlist(title,duration,artist,year,path,timesplayed) 
                    VALUES(?,?,?,?,?,?)''', (data[0], data[1], data[2], data[3], data[4], 0))
        self.conn.commit()

#-----------------------------------------------------------------------------------------------------------------------#
    def makeCover(self, track_name, artist_name, path):
        self.disp.SetBitmap(wx.Bitmap(wx.Image(300, 300)))
        url = 'http://ws.audioscrobbler.com/2.0/?method=track.getInfo&format=json&api_key=5240ab3b0de951619cb54049244b47b5&artist='
        url += urllib.parse.quote(artist_name) + \
            '&track=' + urllib.parse.quote(track_name)
        # print(url)
        link = urllib.request.urlopen(url)
        parsed = json.load(link)
        try:
            tags = ID3(path)
            filename = tags.get("APIC:").data
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
                print(
                    "No album cover could be loaded for the given song from LastFM.")

#-----------------------------------------------------------------------------------------------------------------------#
    def displayimage(self, image):
        self.width, self.height = image.size
        image.thumbnail((200, 200))
        self.PilImageToWxImage(image)

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
    def getSongRecommendationByAlbumArtist(self, track_name, artist_name):
        try:
            # Get album name for reference from LastFM API.
            album_name = ''
            uurl = 'http://ws.audioscrobbler.com/2.0/?method=track.getInfo&limit=10&api_key=5240ab3b0de951619cb54049244b47b5&format=json&artist='
            uurl += urllib.parse.quote(artist_name) + \
                '&track=' + urllib.parse.quote(track_name)

            uurlink = urllib.request.urlopen(uurl)
            pparsed = json.load(uurlink)
            album_name = pparsed['track']['album']['title']

            recommendations = []
            sp = spotipy.Spotify(
                client_credentials_manager=SpotifyClientCredentials())
            off = 0
            found = False
            while (found is False and off < 150):
                # Search for album in spotify.
                album_search = sp.search(
                    q='album:'+album_name+' '+'artist:'+artist_name, limit=50, type='album')
                print(album_search)
                for album in album_search['albums']['items']:
                    album_name_sp = album['name']
                    if artist_name.lower() == str(album['artists'][0]['name']).lower():
                        self.artist_url = album['artists'][0]['id']
                        sp_artist_name = album['artists'][0]['name']
                        found = True
                        break
                off += 50

            artist_seed = []
            artist_seed.append(self.artist_url)
            rec = sp.recommendations(seed_artists=artist_seed, limit=20)

            if len(rec['tracks']) == 0:
                raise Exception

            for track in rec['tracks']:
                if track['preview_url'] is not None:

                    preview_url = track['preview_url']
                    title = track['name']
                    # print(str(track['preview_url']) + ' -- ' + track['name'])
                    art_name = track['album']['artists'][0]['name']
                    data = [art_name, title, preview_url, artist_name]
                    recommendations.append(data)
            self.recommendations.append(recommendations)
            self.fillRecommendationBox(recommendations, artist_name)

        except:
            print("Trying LastFM only as reference.")
            url = 'http://ws.audioscrobbler.com/2.0/?method=track.getsimilar&limit=10&api_key=5240ab3b0de951619cb54049244b47b5&format=json&artist='
            url += urllib.parse.quote(artist_name) + \
                '&track=' + urllib.parse.quote(track_name)

            link = urllib.request.urlopen(url)
            parsed = json.load(link)
            if len(parsed['similartrack']['tracks']) == 0:
                raise Exception("Loading next recommendation method...")
            for track in parsed['similartracks']['track']:
                print(track['name'])


#-----------------------------------------------------------------------------------------------------------------------#


    def songRecommendationByTrackArtist(self, track_name, artist_name):
        artist_url = ''
        recommendations = []
        sp = spotipy.Spotify(
            client_credentials_manager=SpotifyClientCredentials())

        found = False
        off = 0
        while (found is False or off < 150):
            track_search = sp.search(
                q='track:'+track_name+' '+'artist:'+artist_name, limit=50, type='track', offset=off)

            for track in track_search['tracks']['items']:
                artist_url = track['artists'][0]['id']
                found = True
                print(str(artist_url))
                break

            off += 50

        artist_seed = []
        artist_seed.append(artist_url)
        rec = sp.recommendations(seed_artists=artist_seed, limit=20)

        if len(rec['tracks']) == 0:
            raise Exception("No recommendations")

        for track in rec['tracks']:
            if track['preview_url'] is not None:

                preview_url = track['preview_url']
                title = track['name']
                art_name = track['album']['artists'][0]['name']
                data = [art_name, title, preview_url, artist_name]
                recommendations.append(data)

        self.recommendations.append(recommendations)
        self.fillRecommendationBox(recommendations, artist_name)

#-----------------------------------------------------------------------------------------------------------------------#

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

    def onVolume(self, event):
        self.currentVolume = self.volumeCtrl.GetValue()
        self.Player.SetVolume(self.currentVolume/100)

    def onTimer(self, event):
        value = self.Player.Tell()
        self.PlayerSlider.SetValue(value)
        if value > self.Player.Length():
            current = self.playlistBox.GetFocusedItem()
            if current < self.playlistBox.GetItemCount()-1:
                self.playlistBox.SetItemState(
                    current+1, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED)
                self.playlistBox.Select(current, on=0)
                self.playlistBox.Select(current+1, on=1)


app = wx.App()
frame = Scope(None, -1)
frame.Show()
app.MainLoop()
