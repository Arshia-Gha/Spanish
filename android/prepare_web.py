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

    # Android WebView's browser SpeechRecognition implementation is unreliable.
    # In the APK, route the fast conversation mode through Android SpeechRecognizer.
    native_listen = '''  listenSide(side){
    const C=this.state.conv;
    if(C.listening){this.stopListening();return}
    try{if(window.speechSynthesis)window.speechSynthesis.cancel()}catch(e){}
    const src=side==='A'?C.sideALang:C.sideBLang;
    const tgt=side==='A'?C.sideBLang:C.sideALang;
    if(window.AndroidSpeech&&typeof window.AndroidSpeech.start==='function'){
      window.__nativeSpeechPartial=(text)=>this.setState({conv:Object.assign({},this.state.conv,{interim:text||''})});
      window.__nativeSpeechResult=(text)=>{
        this.setState({conv:Object.assign({},this.state.conv,{listening:false,activeSide:null,interim:'',error:''})});
        if(text&&text.trim())this.interpretTurn(side,src,tgt,text.trim());
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
    if(!SR){this.setState({conv:Object.assign({},this.state.conv,{error:'Tu navegador no soporta el micrófono. Usa Chrome o Safari, o escribe abajo.'})});return}
    const rec=new SR();this._rec=rec;rec.lang=src==='es'?'es-ES':src==='fa'?'fa-IR':'en-US';rec.interimResults=true;rec.continuous=false;
    rec.onresult=e=>{let fin='',interim='';for(let i=e.resultIndex;i<e.results.length;i++){const r=e.results[i];if(r.isFinal)fin+=r[0].transcript;else interim+=r[0].transcript;}if(interim)this.setState({conv:Object.assign({},this.state.conv,{interim})});if(fin){this.setState({conv:Object.assign({},this.state.conv,{interim:''})});this.interpretTurn(side,src,tgt,fin.trim());}};
    rec.onerror=ev=>{this.setState({conv:Object.assign({},this.state.conv,{listening:false,activeSide:null,interim:'',error:ev.error==='not-allowed'?'Permiso de micrófono denegado. Actívalo en el navegador.':'No te oí bien, inténtalo otra vez.'})})};
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

    index_path.write_text(index, encoding="utf-8")

    for filename, url in VENDOR.items():
        download(url, OUT / "vendor" / filename)

    print(f"Prepared fast local web bundle at {OUT}")


if __name__ == "__main__":
    main()
