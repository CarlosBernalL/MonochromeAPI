# HIFI Music downloader from monochrome.tf

A python script based in the stack of monochrome.tf for downloading and streaming songs.Leaning in tidal/[HifiAPI](https://github.com/binimum/hifi-api) for metadata and id with audio sourcing from amazon music

## Features
- High Fidelity audio from Amazon Music servers
- Automated downloading ,decrypting(mp4decrypt) ,authenticating(JWT Tokens)...
- Synced Lyrics fetching from [LRCLIB](https://lrclib.net/) and obscure internal monochrome.tf sources...
- Simple deezer downloader as last resort option
- Extensive and detailed metadata tagging including replay_gain (Artist, Album, TrackNº, Copyright, BPM, Key)
- Full resolution thumbnail included!(1280x1280)
- Customizable Folder structure in nombreCancion()

## Requirements

Python libraries:
- **playwright** for easy token retrieval
- **mutagen** for metadata handling

Other requirements:
- [FFmpeg](https://ffmpeg.org/): container conversion (_NO REENCODING_), etc...
- [Bento4 (`mp4decrypt`)](https://www.bento4.com/): Stream decrypting.
- **Bento4 (`mp4dump`)**: KID extraction.


## Usage

In its current state it doesn't have any proper way of user interface right now it is just a module. You can download a song with all the metadata, thumbnail and lyrics file given a Tidal Track ID:
```
    track = obtenerInfoCancion(ID) # -> dict with hifiapi/track info 
    descargarCancion(track,path:str)
```

## Future

First of all try keeping this basic functionality up and running with the constant monochrome.tf changes, new features like adding a proper cli to download music and not just with Tidal ID's, parallel downloading, library updating... and maybe even a TUI will come later on.

In retrospect I should just ditch the entire HIFI API, I haven't done it yet for the same reason that monochrome devs haven't done it, It used to be the backbone of this program and a collection of personal scripts written to manage my library

## Disclaimer

You know, just don't pirate copyrighted content and if you do please support the artist and all that stuff.
This project is strictly for **educational and research purposes**. If you are a monochrome developer and want to chat, feel free to hit me up with a DM!
