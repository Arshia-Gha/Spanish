#!/usr/bin/env python3
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "android" / "app" / "src" / "main" / "assets" / "www"
RUNTIME_COMMIT = "3355cdc9064d409ec1ece7bc8beddba20e80f30f"

VENDOR = {
    "react.production.min.js": "https://unpkg.com/react@18.3.1/umd/react.production.min.js",
    "react-dom.production.min.js": "https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js",
    "babel.min.js": "https://unpkg.com/@babel/standalone@7.29.0/babel.min.js",
}


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "ArshiaEspanol-Android-Build/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response, target.open("wb") as f:
        shutil.copyfileobj(response, f)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    shutil.copy2(ROOT / "index.html", OUT / "index.html")
    for name in ("data", "assets"):
        src = ROOT / name
        if src.exists():
            shutil.copytree(src, OUT / name)

    runtime = subprocess.check_output(
        ["git", "show", f"{RUNTIME_COMMIT}:support.js"], cwd=ROOT, text=True
    )

    runtime = runtime.replace(
        'var REACT_URL = "https://unpkg.com/react@18.3.1/umd/react.production.min.js";',
        'var REACT_URL = "https://app.local/vendor/react.production.min.js";'
    ).replace(
        'var REACT_DOM_URL = "https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js";',
        'var REACT_DOM_URL = "https://app.local/vendor/react-dom.production.min.js";'
    ).replace(
        'var BABEL_URL = "https://unpkg.com/@babel/standalone@7.29.0/babel.min.js";',
        'var BABEL_URL = "https://app.local/vendor/babel.min.js";'
    )
    (OUT / "support.js").write_text(runtime, encoding="utf-8")

    index_path = OUT / "index.html"
    index = index_path.read_text(encoding="utf-8")

    index = re.sub(r'<link rel="preconnect" href="https://fonts\.googleapis\.com">\s*', '', index)
    index = re.sub(r'<link href="https://fonts\.googleapis\.com[^>]+>\s*', '', index)

    index = index.replace("gemini-flash-lite-latest", "gemini-3.5-flash-lite")
    index = index.replace("gemini-flash-latest", "gemini-3.6-flash")

    index = index.replace(
        "generationConfig:{maxOutputTokens:maxTokens||1500,temperature:0.2,thinkingConfig:{thinkingBudget:0}}",
        "generationConfig:{maxOutputTokens:maxTokens||1500,thinkingConfig:{thinkingLevel:model==='gemini-3.6-flash'?'medium':'minimal'}}"
    )
    index = index.replace(
        "generationConfig:{temperature:0,thinkingConfig:{thinkingBudget:0}}",
        "generationConfig:{thinkingConfig:{thinkingLevel:model==='gemini-3.6-flash'?'medium':'minimal'}}"
    )

    # Rápido: Android SpeechRecognizer -> recognized text -> existing translation pipeline.
    native_listen = '''  listenSide(side){
    const C=this.state.conv;
    if(C.listening){this.stopListening();return}
    try{if(window.speechSynthesis)window.speechSynthesis.cancel()}catch(e){}
    const src=side==='A'?C.sideALang:C.sideBLang;
    const tgt=side==='A'?C.sideBLang:C.sideALang;
    if(window.AndroidSpeech&&typeof window.AndroidSpeech.start==='function'){
      window.__nativeSpeechPartial=(text)=>this.setState({conv:Object.assign({},this.state.conv,{interim:text||''})});
      window.__nativeSpeechResult=(text)=>{
        const finalText=(text||'').trim();
        if(!finalText){
          this.setState({conv:Object.assign({},this.state.conv,{listening:false,activeSide:null,interim:'',error:'No te oí bien, inténtalo otra vez.'})});
          return;
        }
        this.setState({conv:Object.assign({},this.state.conv,{listening:false,activeSide:null,interim:finalText,error:''})},()=>{
          this.interpretTurn(side,src,tgt,finalText);
        });
      };
      window.__nativeSpeechError=(code)=>{
        const denied=code==='permission-denied';
        this.setState({conv:Object.assign({},this.state.conv,{listening:false,activeSide:null,interim:'',error:denied?'Permiso de micrófono denegado. Actívalo en Ajustes de Android.':'No te oí bien, inténtalo otra vez.'})});
      };
      try{
        window.AndroidSpeech.start(src);
        this.setState({conv:Object.assign({},this.state.conv,{listening:true,activeSide:side,error:'',interim:''})});
      }catch(e){
        this.setState({conv:Object.assign({},this.state.conv,{listening:false,activeSide:null,error:'No se pudo iniciar el reconocimiento de voz.'})});
      }
      return;
    }
    const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!SR){this.setState({conv:Object.assign({},this.state.conv,{error:'El reconocimiento de voz no está disponible.'})});return}
    const rec=new SR();this._rec=rec;rec.lang=src==='es'?'es-ES':src==='fa'?'fa-IR':'en-US';rec.interimResults=true;rec.continuous=false;
    rec.onresult=e=>{let fin='',interim='';for(let i=e.resultIndex;i<e.results.length;i++){const r=e.results[i];if(r.isFinal)fin+=r[0].transcript;else interim+=r[0].transcript;}if(interim)this.setState({conv:Object.assign({},this.state.conv,{interim})});if(fin){this.setState({conv:Object.assign({},this.state.conv,{interim:''})});this.interpretTurn(side,src,tgt,fin.trim());}};
    rec.onerror=ev=>{this.setState({conv:Object.assign({},this.state.conv,{listening:false,activeSide:null,interim:'',error:ev.error==='not-allowed'?'Permiso de micrófono denegado. Actívalo en Ajustes de Android.':'No te oí bien, inténtalo otra vez.'})})};
    rec.onend=()=>{this.setState({conv:Object.assign({},this.state.conv,{listening:false,activeSide:null,interim:''})})};
    try{rec.start();this.setState({conv:Object.assign({},this.state.conv,{listening:true,activeSide:side,error:'',interim:''})})}catch(e){}
  }
  stopListening(){try{if(window.AndroidSpeech&&typeof window.AndroidSpeech.stop==='function')window.AndroidSpeech.stop()}catch(e){}try{this._rec&&this._rec.stop()}catch(e){}this.setState({conv:Object.assign({},this.state.conv,{listening:false,activeSide:null})})}'''

    index, count = re.subn(
        r'  listenSide\(side\)\{.*?\n  stopListening\(\)\{.*?\n  \}',
        native_listen,
        index,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError(f"Could not patch Android speech mode; matches={count}")

    # Preciso: native Android recorder -> MP4/AAC -> existing Gemini transcription.
    native_record = '''  async recordSide(side){
    const C=this.state.conv;
    const nativeAudio=window.AndroidSpeech&&typeof window.AndroidSpeech.startRecording==='function'&&typeof window.AndroidSpeech.stopRecording==='function';
    if(C.recording){
      if(nativeAudio){try{window.AndroidSpeech.stopRecording()}catch(e){};return}
      try{this._mr&&this._mr.state!=='inactive'&&this._mr.stop()}catch(e){}return;
    }
    if(!this.geminiKey()){this.setState({conv:Object.assign({},C,{error:'Añade tu clave de Google Gemini (Diccionario → "Configurar clave") para el motor Preciso.'})});return}
    const src=side==='A'?C.sideALang:C.sideBLang;
    const tgt=side==='A'?C.sideBLang:C.sideALang;
    try{if(window.speechSynthesis)window.speechSynthesis.cancel()}catch(e){}
    if(nativeAudio){
      window.__nativeRecordingResult=(b64,mime)=>{
        try{
          const raw=atob(b64||'');
          const bytes=new Uint8Array(raw.length);
          for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);
          const blob=new Blob([bytes],{type:mime||'audio/mp4'});
          this.setState({conv:Object.assign({},this.state.conv,{recording:false,activeSide:null,error:''})},()=>this.transcribeGemini(side,src,tgt,blob));
        }catch(e){
          this.setState({conv:Object.assign({},this.state.conv,{recording:false,activeSide:null,error:'No se pudo preparar el audio grabado.'})});
        }
      };
      window.__nativeRecordingError=(code)=>{
        const denied=code==='permission-denied';
        this.setState({conv:Object.assign({},this.state.conv,{recording:false,activeSide:null,error:denied?'Permiso de micrófono denegado. Actívalo en Ajustes de Android.':'No se pudo grabar el audio. Inténtalo otra vez.'})});
      };
      try{
        window.AndroidSpeech.startRecording();
        this.setState({conv:Object.assign({},C,{recording:true,activeSide:side,error:''})});
      }catch(e){
        this.setState({conv:Object.assign({},C,{recording:false,activeSide:null,error:'No se pudo iniciar la grabación.'})});
      }
      return;
    }
    try{
      const stream=await navigator.mediaDevices.getUserMedia({audio:true});
      let mime='';
      ['audio/webm;codecs=opus','audio/webm','audio/mp4','audio/ogg;codecs=opus'].some(m=>{if(window.MediaRecorder.isTypeSupported&&MediaRecorder.isTypeSupported(m)){mime=m;return true}return false});
      const mr=mime?new MediaRecorder(stream,{mimeType:mime}):new MediaRecorder(stream);
      this._mr=mr;this._chunks=[];
      mr.ondataavailable=e=>{if(e.data&&e.data.size)this._chunks.push(e.data)};
      mr.onstop=async()=>{try{stream.getTracks().forEach(t=>t.stop())}catch(e){}const blob=new Blob(this._chunks,{type:mr.mimeType||mime||'audio/webm'});this.setState({conv:Object.assign({},this.state.conv,{recording:false,activeSide:null})});await this.transcribeGemini(side,src,tgt,blob);};
      mr.start();
      this.setState({conv:Object.assign({},this.state.conv,{recording:true,activeSide:side,error:''})});
    }catch(e){this.setState({conv:Object.assign({},this.state.conv,{recording:false,activeSide:null,error:'Permiso de micrófono denegado. Actívalo en Ajustes de Android.'})})}
  }'''

    index, count = re.subn(
        r'  async recordSide\(side\)\{.*?\n  \}\n  async transcribeGemini',
        native_record + '\n  async transcribeGemini',
        index,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError(f"Could not patch Android precise recorder; matches={count}")

    # The APK has Android permissions, not browser permissions.
    index = index.replace('Permiso de micrófono denegado. Actívalo en el navegador.',
                          'Permiso de micrófono denegado. Actívalo en Ajustes de Android.')

    index_path.write_text(index, encoding="utf-8")

    for filename, url in VENDOR.items():
        download(url, OUT / "vendor" / filename)

    print(f"Prepared fast local web bundle at {OUT}")


if __name__ == "__main__":
    main()
