import time
import random
import asyncio
import httpx
from pathlib import Path
from mutagen.flac import FLAC, Picture
import traceback
import shutil

from playwright.async_api import async_playwright
from lyrics import obtenerLetra

API_AMZN = "https://amz.geeked.wtf/"
API_TIDAL = "https://api.monochrome.tf"
LIBRARY_PATH = "musica/"

class ClienteDescargas:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.contexto_global = None
        self.pestana_activa = None
        
        self.token_jwt = None
        self.lock_renovacion = asyncio.Lock()
        
        self.http = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self):#init playwright y chequea paquetes
        if not shutil.which("mp4dump"):
            raise FileNotFoundError("mp4dump no está instalado")

        if not shutil.which("mp4decrypt"):
            raise FileNotFoundError("mp4decrypt no está instalado")

        if not shutil.which("ffmpeg"):
            raise FileNotFoundError("ffmpeg no está instalado")

        self.playwright = await async_playwright().start()
        puerto_oculto = random.randint(30000, 60000)
        
        self.contexto_global = await self.playwright.chromium.launch_persistent_context(
            user_data_dir="./mi_perfil",
            channel="chrome", 
            headless=False, #Con headless no es capaz de obtener el token
            args=[f"--remote-debugging-port={puerto_oculto}", "--disable-blink-features=AutomationControlled"]
        )
        self.pestana_activa = await self.contexto_global.new_page()

        

        await self._obtener_jwt(1)
        return self
    



    async def __aexit__(self, exc_type, exc_val, exc_tb):#playwright close
        
        await self.pestana_activa.close()
        await self.http.aclose()
        if self.contexto_global:
            await self.contexto_global.close()
        if self.playwright:
            await self.playwright.stop()

    def rutaCancion(self,cancion:dict) -> str:
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

    async def _obtener_jwt(self,token_viejo):

        if token_viejo == self.token_jwt:
            return
        
        async with self.lock_renovacion:
            try:
                await self.pestana_activa.goto("https://monochrome.tf/track/536958137")
                await self.pestana_activa.wait_for_function(
                    "() => window.localStorage.getItem('amazon_turnstile_jwt') !== null", 
                    timeout=30000
                )
                self.token_jwt = await self.pestana_activa.evaluate("window.localStorage.getItem('amazon_turnstile_jwt')")
                                
                print("[\033[92m✓\033[00m] ¡Nuevo JWT obtenido y guardado en memoria!")
            except Exception as e:
                print(f"[\033[91mX\033[00m] Error al obtener el JWT en Playwright: {e}")
                raise e

    async def obtenerInfoCancion(self, id):
        try:
            respuesta = await self.http.get(f"{API_TIDAL}/info/", params={'id': id})
            respuesta.raise_for_status()
            return respuesta.json()['data']
        except Exception as e:
            print(f"Ha habido una excepcion al tratar de obtener informacion para una cancion con la api de tidal de id {id} con la excepcion:\n{e}")
            raise e
    async def _amazon(self,cancion:dict,ruta:str) -> bool:
            
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
            'x-turnstile-jwt': self.token_jwt
        }


        f = await self.http.get(f"{API_AMZN}api/track/",params={
            "track":cancion['title'],
            "duration":cancion['duration'],
            "album":cancion['album']['title'],
            #"artist":cancion['artist']['name'],
            "artist":artistas,
            "quality":"UHD",
            },headers=headers)
        
        if f.status_code == 401 or f.status_code == 428:
            self.token_jwt = None 
            await self._obtener_jwt(self.token_jwt)
            return await self._amazon(cancion,ruta)
        
        if f.status_code == 404:
            print(f"Canción no encontrada en Amazon  {cancion['title']}")
            return False
        
        response = f.json()

        async with self.http.stream("GET", response['stream_url']) as cancionCifrada:
            cancionCifrada.raise_for_status()
            with open(f"{ruta}.mp4", "wb") as archivo: 
                async for chunk in cancionCifrada.aiter_bytes(chunk_size=65536):
                    archivo.write(chunk)
        # Procesamientos externos mediante subprocesos (bloqueantes pero rápidos, corren en su propio proceso)
        await self._descifrarCancion(f"{ruta}.mp4", response["decryption_key"])
        await self._mp4toflac(ruta)
        
 
        # Inyección de ReplayGain
        db_ganancia = -18.0 - float(response["replay_gain"]['program_loudness_lufs'])    
        audio = FLAC(f"{ruta}.flac")
        audio["REPLAYGAIN_TRACK_GAIN"] = f"{db_ganancia:.2f} dB"
        audio["REPLAYGAIN_TRACK_PEAK"] = "1.000000"
        await asyncio.to_thread(audio.save)
        return True


    async def _deezer_fallback(self, cancion: dict, ruta: str):
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0',
            'Origin': 'https://monochrome.tf',
        }
        try :
            respuesta = await self.http.get('https://dzr.tabs-vs-spaces.wtf/stream/', params={
                'isrc': cancion['isrc'],
                'format': 'FLAC',
            }, headers=headers)
            
            respuesta.raise_for_status()
            if respuesta.headers.get('Content-Type') == 'audio/mpeg':
                with open(f"{ruta}.mp3", 'wb') as f:
                    f.write(respuesta.content)
            else:    
                with open(f"{ruta}.flac", 'wb') as f:
                    f.write(respuesta.content)

        except Exception as e:
                print(f"\033[91m[!] Error en el fallback de Deezer para {ruta}!")
                raise e
                
    async def _descifrarCancion(self, ruta: str, key: str):#ruta:mp4,key:KIDkey -> .mp4descifrado
        try:

            mp4dump  = await asyncio.create_subprocess_exec("mp4dump", ruta,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            kidcomando,stderr = await mp4dump.communicate()
            if mp4dump.returncode != 0:
                raise RuntimeError(f"El proceso de mp4dump falló con error: {stderr.decode('utf-8')}")

            kidcomando = kidcomando.decode('utf-8')
            todas = kidcomando.splitlines()
            kid = [linea for linea in todas if "KID" in linea]
            if not kid:
                print(f"Error al obtener el KID del archivo {ruta}, probablemente este corrupto!")
                return
            kid_limpio = kid[0].split("[")[1].split("]")[0].replace(" ", "")

            mp4decrypt = ["--key", f"{kid_limpio}:{key}", ruta, f"{ruta}descifrado"]
            proceso = await asyncio.create_subprocess_exec("mp4decrypt", *mp4decrypt,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            stdout ,stderr2 = await proceso.communicate()
            if proceso.returncode != 0:
                raise RuntimeError(f"El proceso de mp4decrypt falló con error: {stderr.decode('utf-8')}")

            Path(ruta).unlink()
            Path(f"{ruta}descifrado").rename(ruta)
        except Exception as e:
            print(f"\033[91m[!] Error en mp4dump/mp4decrypt:\033[00m \n Excepcion:\n{repr(e)}\nStderr mp4dump:\n {stderr}\nStderr mp4decrypt:\n {stderr2}")
            
            raise e
    async def _mp4toflac(self,ruta):# ruta:mp4 -> flac
        try:
            ffmpeg_args = [
                #"ffmpeg",
                "-y",          
                "-v", "error", 
                "-i", f"{ruta}.mp4",
                "-c:a", "flac",
                f"{ruta}.flac",
            ]
            

            #subprocess.run(ffmpeg, check=True, capture_output=True, text=True)
            proceso = await asyncio.create_subprocess_exec("ffmpeg", *ffmpeg_args,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
            stdout,stderr  =await proceso.communicate()

            Path(f"{ruta}.mp4").unlink()
        except Exception as e:
            print(f"\033[91m[!] Ha habido un error al usar ffmpeg!\033[00m \n {repr(e)}, ,\n {stderr}")
            raise e


    async def append_metadata(self,info,path):# appends metadata to .flac file given info in the format of the TidalAPI/HifiAPI
        audio = FLAC(path)

        image = Picture()
        idd = info['album']['cover'].replace("-","/")
        url = "http://resources.tidal.com/images/"+idd+"/1280x1280.jpg"
        respuesta = await self.http.get(url)
        image.data = respuesta.content
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

        #audio.save()
        await asyncio.to_thread(audio.save)


    # Pre: rellenar la maxima cantidad de argumentos posibles
    # Post: devuelve dict con esquema de api de tidal de la opcion mas probable
    async def tidalSearchTrack(self,title:str,artist:str=None,album:str=None):# -> tipo dict con cancion tidal
        params = {}
        if title:
            params['s'] = title
        if artist:
            params['a'] = artist    
        if album: 
            params["al"] = album     
        try: 
            respuesta = await self.http.get(f"{API_TIDAL}/search/",params=params)
            respuesta.raise_for_status()
            opciones = respuesta.json()['data']['items']
            return opciones[0] # la mas probable de coincidir [0]
        except Exception as e:
            print(f"Ha habido una excepcion al tratar de buscar  una cancion con la api de tidal de nombre {title} con la excepcion:\n{e}")



        
    async def descargarCancion(self, id:int, ruta: str = None):
        letra_tarea = None
        try:
            Tstart = time.perf_counter()
            cancion = await self.obtenerInfoCancion(id)
            if not ruta:
                ruta = self.rutaCancion(cancion)
            letra_tarea= asyncio.create_task(obtenerLetra(cancion,ruta))

            Path(ruta).parent.mkdir(parents=True, exist_ok=True)

            ok = await self._amazon(cancion, ruta)
            if not ok:
                await self._deezer_fallback(cancion, ruta)
                return

            await self.append_metadata(cancion, f"{ruta}.flac")


            size = round(Path(f"{ruta}.flac").stat().st_size / 1048576, 2)
            Ttotal = time.perf_counter() - Tstart
            print(f"[\033[92m✓\033[00m] {ruta}.flac \033[93m{str(size)} MB\033[00m en {round(Ttotal,2)}s. ({round(size/Ttotal,2)} MB/s)")    


        except Exception as e:
            if ruta:
                print(f"[\033[91mX\033[00m] {ruta} ")    
            else:
                print(f"[\033[91mX\033[00m] Con ruta desconocida!")    
            if cancion:
                print(f"Tidal id: {cancion['id']}")    
            traceback.print_exc()
        
        finally:
            if letra_tarea:
                await letra_tarea