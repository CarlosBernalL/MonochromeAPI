# HIFI Music downloader module from monochrome.tf

A python script based in the stack of monochrome.tf for downloading and streaming songs .Leaning in tidal/[HifiAPI](https://github.com/binimum/hifi-api) for metadata and id with audio sourcing from amazon music

## Features
- High Fidelity audio flacs from Amazon Music servers
- Automated downloading ,decrypting(mp4decrypt) ,authenticating(JWT Tokens)...
- Synced Lyrics fetching from [LRCLIB](https://lrclib.net/) and obscure internal monochrome.tf sources...
- Simple deezer downloader as last resort option(sketchy AF)
- Extensive and detailed metadata tagging including replay_gain (Artist, Album, TrackNº, Copyright, BPM, Key)
- Full resolution thumbnail included!(1280x1280)
- Customizable Folder structure in rutaCancion()
- Now with Working async downloading. (Working doesn't mean finished)

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
    async with ClienteDescargas() as cliente:
        await cliente.descargarCancion(id=id_tidal_cancion,path)
        #path is optional.In case of not being provided it will save the song in the defined schema in rutacancion() 
```

## Future

First of all try keeping this basic functionality up and running with the constant monochrome.tf changes.
Adding **utilities** for actually being able to **interface as an user** with the library will be nice. I am planning first in a cli and maybe later on a tui but I am problably going to prioritize adding cool features to the cli app like spotify playlist scraping.SoonTm.

## Thoughts
I am still very reliant on HIFIAPI, It is the entire backbone of the library and I don't know if I am comfortable with that... (even though it has the advantage of 1280p thumbnails) 


## Disclaimer

You know, just don't pirate copyrighted content and if you do please support the artist and all that stuff.
This project is strictly for **educational and research purposes**. If you are a monochrome developer and want to chat, feel free to hit me up with a DM!
