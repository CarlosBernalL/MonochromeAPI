import requests
import subprocess
import re
from playwright.sync_api import sync_playwright
import random
import time
from pathlib import Path
from mutagen.flac import FLAC,Picture
import traceback
from lyrics import obtenerLetra
import asyncio
API_AMZN = "https://amz.geeked.wtf/"
API_TIDAL = "https://api.monochrome.tf"
LIBRARY_PATH = "musica/"

def rutaCancion(cancion:dict) -> str:
    #configurable como quieras pero omite la extension y el punto. Opciones:
    #       id Tidal: cancion['id']
    #       titulo  : cancion['title']
    #       duracion: cancion['duration']
    #       trackNum: cancion['trackNumber']
    #       isrc    : cancion['isrc']
    #       artista : cancion['artist']['name']
    #       +artista: cancion['artists'][<nºartista>]['name']
    #       album   : cancion['album']['title']
    return f"{LIBRARY_PATH}{cancion['artists'][0]['name']}/{cancion['album']['title']}/{str(cancion['trackNumber'])} - {cancion['title']}" 

def obtenerInfoCancion(id):

    f =requests.get(API_TIDAL+'/info/',params={'id':id})
    if(f.status_code==200):
        info = f.json()['data']    
        return info
    
def amazon(cancion:dict,ruta:str) -> bool:
    with open("jwt.txt", "r", encoding="utf-8") as archivo:
        jwt = archivo.read()
    
    artistas  = ", ".join(artista["name"] for artista in cancion['artists'])
    headers = {
        'accept': '*/*',
        'accept-language': 'es-ES,es;q=0.9',
        'cache-control': 'no-cache',
        'origin': 'https://monochrome.tf',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'sec-ch-ua': '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'cross-site',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
        'x-turnstile-jwt': jwt
    }

    f = requests.get(API_AMZN+"api/track/",params={
        "track":cancion['title'],
        "duration":cancion['duration'],
        "album":cancion['album']['title'],
        #"artist":cancion['artist']['name'],
        "artist":artistas,
        "quality":"UHD",
        },headers=headers)
    if f.status_code == 401 or f.status_code == 428:
        obtener_jwt()
        time.sleep(10)
        return amazon(cancion,ruta)
    
    if f.status_code != 200:
        print(f"Cancion no encontrada. con id {cancion['id']}")
        return False
    
    response = f.json()

    cancionCifrada = requests.get(response['stream_url'], stream=True)
    if cancionCifrada.status_code == 200:
        with open(f"{ruta}.mp4", 'wb') as f:
            for chunk in cancionCifrada.iter_content(chunk_size=8192):
                f.write(chunk)

    descifrarCancion(f"{ruta}.mp4",response["decryption_key"])
    mp4toflac(ruta)
    Path(f"{ruta}.mp4").unlink()
    #de esta poca metadata nos tenemos que ocupar aqui porque solo la tenemos en este momento y es especifica del archivo del servidor de amzn,distinta del resto de metadata de tdal 
    db_ganancia = -18.0 - float(response["replay_gain"]['program_loudness_lufs'])    
    audio = FLAC(f"{ruta}.flac")
    audio["REPLAYGAIN_TRACK_GAIN"] = f"{db_ganancia:.2f} dB"
    audio["REPLAYGAIN_TRACK_PEAK"] = "1.000000" #asumimos 
    audio.save()
    return True #todo ok

def deezer_fallback(cancion:dict,ruta:str):# -> low quality song.        fallback de ultimo recurso a deezer
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0',
        'Accept': 'audio/webm,audio/ogg,audio/wav,audio/*;q=0.9,application/ogg;q=0.7,video/*;q=0.6,*/*;q=0.5',
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://monochrome.tf',
        'Sec-GPC': '1',
        'Sec-Fetch-Dest': 'audio',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site',
        'Range': 'bytes=0-',
        'Connection': 'keep-alive',
    }

    respuesta = requests.get('https://dzr.tabs-vs-spaces.wtf/stream/', params={
        'isrc': cancion['isrc'],
        'format': 'FLAC',
    }, headers=headers)
    if(respuesta.status_code > 299):
        print(f"\033[91m[!] Ha habido un error al tratar de obtener {ruta} con nuestra ultima alternativa!")
        return
    if respuesta.headers.get('Content-Type') == 'audio/mpeg':
        with open(f"{ruta}.mp3", 'wb') as f:
            f.write(respuesta.content)
    else:    
        with open(f"{ruta}.flac", 'wb') as f:
            f.write(respuesta.content)


def descifrarCancion(ruta:str,key:str):# -> decrypted .mp4 file containing a flac audio track
    #descifra un archivo com mp4dump obtenido de los servers de amzn
    try:
        mp4dump=[
            "mp4dump",
            ruta,
        ]
        kidcomando = subprocess.run(mp4dump,capture_output=True,text=True,check=True)     
        todas = kidcomando.stdout.splitlines()
        kid = [linea for linea in todas if "KID" in linea]
        if not kid:
            print(f"Error al obtener el kid del archivo {ruta}, seguramente el archivo este corrupto!")
        kid = kid[0].split("[")[1].split("]")

        kid_limpio = kid[0].replace(" ", "")

        mp4decrypt = [
            "mp4decrypt",
            "--key",str(kid_limpio)+":"+key,            
            ruta,
            f"{ruta}descifrado",            
        ]
        subprocess.run(mp4decrypt, check=True)

        Path(ruta).unlink()
        Path(f"{ruta}descifrado").rename(ruta)
    except Exception as e:
        print(f"\033[91m[!] Ha habido un error al usar mp4dump!\033[00m \n {repr(e)}")

def mp4toflac(ruta):# extracts flac track from mp4 container
    try:
        ffmpeg = [
            "ffmpeg",
            "-y",          
            "-v", "error", 
            "-i", f"{ruta}.mp4",
            "-c:a", "flac",
            f"{ruta}.flac",
        ]
        

        subprocess.run(ffmpeg, check=True, capture_output=True, text=True)
    except Exception as e:
        print(f"\033[91m[!] Ha habido un error al usar ffmpeg!\033[00m \n {repr(e)}")


def append_metadata(info,path):# appends metadata to .flac file given info in the format of the TidalAPI/HifiAPI
    audio = FLAC(path)

    image = Picture()
    idd = info['album']['cover'].replace("-","/")
    url = "http://resources.tidal.com/images/"+idd+"/1280x1280.jpg"
    image.data = requests.get(url).content
    image.type = 3 
    image.mime = "image/jpeg" # O "image/png" 
    image.desc = "Front Cover"
    audio.add_picture(image)

    #metadata especifica para el master de tidal
    #audio["replaygain_track_gain"] = str(info['replayGain'])
    #audio["replaygain_track_peak"] = str(info['peak'])
    #audio["replaygain_album_gain"] = str(info['albumReplayGain'])
    #audio["replaygain_album_peak"] = str(info['albumPeakAmplitude'])

    audio["title"] = info['title']
    audio["TRACKNUMBER"]= str(info['trackNumber'])
    audio["DISCNUMBER"]= str(info['volumeNumber'])
    audio["COPYRIGHT"]= str(info["copyright"])
    audio["SERVER_ID"]= str(info['id'])
    audio["albumartist"] = str(info['artist']['name'])

    audio["EXPLICIT"] = ["1" if info["explicit"] else "0"]    
    audio["DJREADY"] = ["1" if info["djReady"] else "0"]
    audio["STEMREADY"] = ["1" if info["stemReady"] else "0"]
    audio["BPM"] = [str(info['bpm'])]
    audio["KEY"] = [str(info['key'])]
    audio["ISRC"] = [str(info['isrc'])]

    a=[]
    for artista in info['artists']:
        a.append(artista['name'])
    audio["ARTIST"]=a
    
    audio["ALBUM"] = info['album']['title']
    audio["DATE"] = info['streamStartDate'][:10]

    audio.save()



def obtener_jwt():#obtains a new jwt token from monochrome.tf to use its amazon music endpoint
    global pestana_activa 
    
    pestana_activa.goto("https://monochrome.tf/track/536958137")
    pestana_activa.wait_for_function("() => window.localStorage.getItem('amazon_turnstile_jwt') !== null")
    jwt_crudo = pestana_activa.evaluate("window.localStorage.getItem('amazon_turnstile_jwt')")
    
    with open("jwt.txt", "w", encoding="utf-8") as f:
        f.write(jwt_crudo)
        
    print("[\033[92m✓\033[00m] ¡Nuevo JWT obtenido y guardado!")
    
    return
def tidalSearchTrack(title:str,artist:str=None,album:str=None):
    params = {}
    if title:
        params['s'] = title
    if artist:
        params['a'] = artist    
    if album: 
        params["al"] = album     

    respuesta = requests.get(f"{API_TIDAL}/search/",params=params)
    respuesta.raise_for_status()
    return respuesta.json()['data']['items'][0] # la mas probable de coincidir [0]

# Pre: cancion=SONG ID FROM TIDAL       ;   ruta=absolute or relative path to save audio file and lyrics file if possible. provide path without extension and without dot Ej: "Ed Sheeran/Shape of you"
# Post:
# <ruta>.flac music file downloaded from amazon music servers at maximum quality or from deezer with questionable audio quality as a fallback  
# <ruta>.lrc LRC synced lyrics file from lrclib.net or from internal monochrome.tf databases



async def descargarCancion(title:str,artist:str,album:str=None,ruta:str=None):
    try:
        Tstart = time.perf_counter()
        cancion = tidalSearchTrack(title,artist,album)

        if not ruta:
            ruta=rutaCancion(cancion)

        if not album:
            album=cancion['album']['title']
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)

        ok = amazon(cancion,ruta)
        if not ok:
            deezer_fallback(cancion,ruta) 
            # fallback de ultimo recurso sin metadata,se podria realizar una funcion para añadir metadata.
            obtenerLetra(cancion,ruta)

            return
        asyncio.run(append_metadata(cancion,f"{ruta}.flac"))
        asyncio.run(obtenerLetra(cancion,ruta))

        size=round(Path(f"{ruta}.flac").stat().st_size/1048576,2)
        Tstop = time.perf_counter()
        Ttotal = Tstop - Tstart
        print(f"[\033[92m✓\033[00m] {ruta}.flac \033[93m{str(size)} MB\033[00m en {round(Ttotal,2)}s . De media {round(size/Ttotal,2)} MB/s")    

    except Exception as e:
        print("[\033[91mX\033[00m] "+ruta+" \033[91m"+str(e)+" \033[00m")
        print(f"Tidal id: {cancion['id']}")    
        traceback.print_exc()





p = sync_playwright().start()
puerto_oculto = random.randint(30000, 60000)
contexto_global = p.chromium.launch_persistent_context(
    user_data_dir="./mi_perfil",
    channel="chrome", 
    headless=False,
    args=[f"--remote-debugging-port={puerto_oculto}","--disable-blink-features=AutomationControlled"]
)
pestana_activa = contexto_global.new_page()



