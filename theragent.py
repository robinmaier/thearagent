import base64
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
import os
import pyaudio
import wave
from datetime import datetime
import json


# .env Datei laden
load_dotenv()

# OpenAI Client initialisieren mit API Key aus .env
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def record_audio():
    # Audio-Parameter
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    
    # PyAudio Objekt erstellen
    p = pyaudio.PyAudio()
    
    input("Willkommen bei TherAgent. Über was möchtest du gerne sprechen? Drücke Enter um die Aufnahme zu starten...")
    
    # Aufnahme-Stream öffnen
    stream = p.open(format=FORMAT,
                   channels=CHANNELS,
                   rate=RATE,
                   input=True,
                   frames_per_buffer=CHUNK)

    print("\nAufnahme läuft... Drücke CTRL+C zum Stoppen.")
    
    frames = []
    
    # Aufnahme-Schleife
    while True:
        try:
            data = stream.read(CHUNK)
            frames.append(data)
        except KeyboardInterrupt:
            break
    
    print("\nAufnahme beendet!")
    
    # Stream schließen
    stream.stop_stream()
    stream.close()
    
    # Ordner erstellen, falls nicht vorhanden
    if not os.path.exists('audio_input'):
        os.makedirs('audio_input')
    
    # Dateiname mit Zeitstempel generieren
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"audio_input/recording_{timestamp}.wav"
    
    # WAV-Datei speichern
    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    
    # PyAudio Objekt schließen
    p.terminate()
    
    print(f"Audio wurde gespeichert als: {filename}")
    return filename

def get_latest_recording():
    # Pfad zum audio_input Ordner
    input_dir = "audio_input"
    
    try:
        # Alle wav-Dateien im Ordner finden
        wav_files = list(Path(input_dir).glob("*.wav"))
        
        if not wav_files:
            raise FileNotFoundError("Keine WAV-Dateien im audio_input Ordner gefunden")
        
        # Neueste Datei nach Erstellungsdatum finden
        latest_file = max(wav_files, key=lambda x: x.stat().st_mtime)
        print(f"Neueste Aufnahme gefunden: {latest_file}")
        return str(latest_file)
    
    except FileNotFoundError:
        print(f"Fehler: Der Ordner {input_dir} existiert nicht oder ist leer")
        raise

def validate_wav(file_path):
    try:
        with wave.open(file_path, 'rb') as wav_file:
            print(f"Channels: {wav_file.getnchannels()}")
            print(f"Sample width: {wav_file.getsampwidth()}")
            print(f"Frame rate: {wav_file.getframerate()}")
        return True
    except Exception as e:
        print(f"Ungültiges WAV-Format: {str(e)}")
        return False

def save_analysis(analysis, input_file):
    output_dir = "analyze_audio_output"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"{output_dir}/{Path(input_file).stem}_analysis_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": timestamp,
            "input_file": str(input_file),
            "analysis": analysis
        }, f, ensure_ascii=False, indent=2)
    return output_file


def analyze_audio():
    print("Starte Audio-Analyse...")
    
    try:
# Neueste Aufnahme finden
        file_path = get_latest_recording()
        print(f"Versuche Datei zu öffnen: {file_path}")

        with open(file_path, "rb") as audio_file:
            audio_data = audio_file.read()
            encoded_audio = base64.b64encode(audio_data).decode('utf-8')
        
        print("Audio erfolgreich eingelesen und encodiert")
        # Transkription und Analyse durchführen
        completion = client.chat.completions.create(
            model="gpt-4o-audio-preview",
            modalities=["text"],
            #audio={"voice": "alloy", "format": "wav"}, #include if audio-ouput is needed
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please transcribe this audio and analyze its tonality and emotional state. Provide the analysis in this format: 1. Transcription: [text] 2. Tonality: [description] 3. Emotional State: [description]"
                        },
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": encoded_audio,
                                "format": "wav"
                            }
                        }
                    ]
                }
            ]
        )

        # Ergebnis ausgeben
        response = completion.choices[0].message.content
        print(response)
        output_file = save_analysis(response, file_path)
        print(f"Analyse wurde gespeichert als: {output_file}")

    except FileNotFoundError:
        print(f"Fehler: Die Datei wurde nicht gefunden. Bitte stellen Sie sicher, dass {file_path} existiert.")
    except Exception as e:
        print(f"Ein Fehler ist aufgetreten: {str(e)}")

def get_latest_analysis():
    analysis_files = list(Path("analyze_audio_output").glob("*.json"))
    if not analysis_files:
        raise FileNotFoundError("Keine Analyse-Dateien gefunden")
    latest_file = max(analysis_files, key=lambda x: x.stat().st_mtime)
    
    with open(latest_file, 'r', encoding='utf-8') as f:
        return json.load(f)
    
def generate_response():
    try:
        # Letzte Analyse laden
        analysis = get_latest_analysis()
        
        # Therapeuten-Antwort mit Audio generieren
        completion = client.chat.completions.create(
            model="gpt-4o-audio-preview",
            modalities=["text", "audio"],
            audio={"voice": "alloy", "format": "wav"},
            messages=[
                {
                    "role": "system",
                    "content": "Versetze dich in die Rolle eines Psychotherapeuten und reagiere mit einer kurzen Antwort, um das Gespräch fortzuführen"
                },
                {
                    "role": "user",
                    "content": f"Basierend auf dieser Analyse: {analysis['analysis']}"
                }
            ]
        )
        

        # Text-Antwort speichern
        response_text = completion.choices[0].message.audio.transcript
        print("\nTherapist response:", response_text)
        
        # Audio-Antwort speichern
        output_dir = "therapist_output"
        os.makedirs(output_dir, exist_ok=True)
        timestamp = Path(analysis['input_file']).stem
        output_file = f"{output_dir}/response_{timestamp}.wav"
        
        # WAV-Datei aus base64 decodieren und speichern
        wav_bytes = base64.b64decode(completion.choices[0].message.audio.data)
        with open(output_file, "wb") as f:
            f.write(wav_bytes)
            
        print(f"\nAudio-Antwort gespeichert in: {output_file}")
        return output_file
        
    except Exception as e:
        print(f"Fehler: {str(e)}")



if __name__ == "__main__":
    print("Programm startet")
    record_audio()
    analyze_audio()
    generate_response()