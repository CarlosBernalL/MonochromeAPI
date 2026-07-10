LYRICS_DEBUG = False
import requests
import re

async def obtenerLetra(cancion,ruta):# tries to download lyrics from lrclib.net and internal monochrome.tf databases given a dict containing the track info given by tidalAPI/hifiAPI

    try:
        respuesta = requests.get("https://lrclib.net/api/get", params={
        'track_name':cancion['title'],
        'artist_name':cancion['artist']['name'],
        'album_name':cancion['album']['title'],
        'duration':cancion['duration']

    }, timeout=30)
        respuesta.raise_for_status()
        datos = respuesta.json()
        letra = datos.get('syncedLyrics') or datos.get('plainLyrics')
        if letra:
            with open(f"{ruta}.lrc", "w", encoding="utf-8") as f:
                f.write(letra)
            return

    except Exception as e:
        if LYRICS_DEBUG:
            print(f"Error al obtener la letra de lrclib.net {repr(e)}")
        else:
            pass 

    try: 
        respuesta = requests.get("https://lyrics-api.binimum.org/", params={
            'track': cancion['title'],
            'artist': cancion['artist']['name'],
            'album': cancion['album']['title'],
            'duration': cancion['duration']
        }, timeout=30)
        respuesta.raise_for_status()
        response_json = respuesta.json() 
        resultados = response_json.get('results', [])
        if resultados:
            url_ttml = resultados[0].get('lyricsUrl')
            if url_ttml:
                ttml = requests.get(url_ttml, timeout=5)
                if ttml.status_code == 200:
                    lrc_data = convertir_ttml_a_lrc(ttml.text)
                    if lrc_data:
                        with open(f"{ruta}.lrc", "w", encoding="utf-8") as f:
                            f.write(lrc_data)
                        return
                    
    except Exception as e:
        if LYRICS_DEBUG:
            print(f"Error al obtener la letra de lyrics-api.binimum.org {repr(e)}")
        else:
            pass 
    try: 
        respuesta = requests.get("https://unison.boidu.dev/lyrics", params={
            'song': cancion['title'],
            'artist': cancion['artist']['name'],
            'album': cancion['album']['title'],
            'duration': cancion['duration']
        }, timeout=30)
        respuesta.raise_for_status()
        datos = respuesta.json()
        letra = datos.get('lrc') or datos.get('lyrics')
        if letra:
            with open(f"{ruta}.lrc", "w", encoding="utf-8") as f:
                f.write(letra)
            return
        
    except Exception as e:
        if LYRICS_DEBUG:
            print(f"Error al obtener la letra de unison.boidu.dev {repr(e)}")
        else:
            pass 

    try:#                               Too many requests..?
        respuesta = requests.get(f"https://lyrist.vercel.app/api/{cancion['title']}/{cancion['artist']['name']}", timeout=5)
        respuesta.raise_for_status()
        datos = respuesta.json()
        letra_plana = datos.get('lyrics')
        if letra_plana:
            with open(f"{ruta}.lrc", "w", encoding="utf-8") as f:
                f.write(f"[00:00.00]{cancion['title']}\n[00:05.00]\n" + letra_plana)
            return
        
    except Exception as e:
        if LYRICS_DEBUG:
            print(f"Error al obtener la letra de lyrist.vercel.app {repr(e)}")
        else:
            pass 

    print(f"[\033[93m!\033[00m] No se encontró la letra para: {cancion['title']}")


def convertir_ttml_a_lrc(ttml_texto):# convert ttml synced lyrics to lrc synced lyrics
    lrc_lineas = []
    patron_p = r'<p[^>]*begin="([^"]+)"[^>]*>(.*?)</p>'
    
    for tiempo_str, bloque_texto in re.findall(patron_p, ttml_texto, re.DOTALL | re.IGNORECASE):
        
        texto_limpio = re.sub(r'<[^>]+>', '', bloque_texto)
        texto_limpio = " ".join(texto_limpio.split()).strip()
        
        if not texto_limpio:
            continue 
            
        try:
            # 2. Lógica de tiempo universal
            partes = tiempo_str.split(':')
            
            if len(partes) == 3:
                # Caso 1: Viene con horas (HH:MM:SS.xxx) 
                horas = int(partes[0])
                minutos = int(partes[1])
                segundos = float(partes[2])
                minutos += horas * 60 
                
            elif len(partes) == 2:
                # Caso 2: Viene con minutos (MM:SS.xxx) 
                minutos = int(partes[0])
                segundos = float(partes[1])
                
            else:
                # Caso 3: Solo segundos (SS.xxx) 
                minutos, segundos = divmod(float(tiempo_str), 60)
                
            #  [MM:SS.xx]
            tiempo_lrc = f"[{int(minutos):02d}:{segundos:05.2f}]"
            lrc_lineas.append(f"{tiempo_lrc} {texto_limpio}")
            
        except ValueError:
            continue 
            
    return "\n".join(lrc_lineas)
