import QtQuick
import Quickshell

// Podgląd sesji gry wbudowany w okno (25.10, Karol: „podgląd odpalany dopiero jak wybieram postać”). Co 1,5 s jedna klatka JPEG z
// `podglad_klatka.sh <id>` (grim na sesji sway instancji, tylko odczyt): lokalnie, a gdy ustawiono RETRONIC_OKNO_PODGLAD_HOST (okno na
// innym komputerze), po ssh. Klatki idą na przemian do dwóch plików, żeby Image zawsze przeładował. Bez `live` nic nie jest pobierane.
Item {
  id: root

  property string instId: ""
  property string repoDir: ""
  property bool live: false
  property int frame: 0
  property bool failed: false
  // szerokość w pikselach ekranu okna; klatka pobierana w skali do natywnych 1175 px (min 0,5, krok 0,1), żeby nie rozciągać małej
  readonly property real skala: Math.max(0.5, Math.min(1.0, Math.ceil(width / 1175 * 10) / 10))

  readonly property string host: Quickshell.env("RETRONIC_OKNO_PODGLAD_HOST") || ""
  readonly property string tmp: (Quickshell.env("XDG_RUNTIME_DIR") || "/tmp")
  function fileFor(n) { return tmp + "/retronic-okno-podglad-" + instId + "-" + (n % 2) + ".jpg" }

  readonly property var script: [
    'out="$3"; if [ -n "$1" ]; then',
    '  ssh -o BatchMode=yes -o ConnectTimeout=5 -o ControlMaster=auto -o ControlPath=/tmp/retronic-zdalny-%C -o ControlPersist=120 "$1" "cd ~/Games/Retronic/pomocnik && ./podglad_klatka.sh $2 $5" > "$out.tmp"',
    'else "$4/podglad_klatka.sh" "$2" "$5" > "$out.tmp"; fi && [ -s "$out.tmp" ] && mv "$out.tmp" "$out"'
  ].join("\n")

  function fetch() {
    if (!live || !/^[a-z0-9_-]+$/.test(instId)) return
    job.start(["sh", "-c", script, "retronic-podglad", host, instId, fileFor(frame + 1), repoDir, String(skala)], instId)
  }

  onInstIdChanged: { frame = 0; failed = false }
  onLiveChanged: if (live) fetch()

  Job {
    id: job
    timeoutMs: 6000
    timeoutText: "timeout"
    onFinished: function(text, tag) {
      if (tag !== root.instId) return
      if (text === "timeout") { root.failed = true; return }
      root.failed = false
      root.frame = root.frame + 1
    }
  }
  Timer { interval: 1500; repeat: true; running: root.live; onTriggered: root.fetch() }

  Image {
    anchors.fill: parent
    visible: root.frame > 0
    source: root.frame > 0 ? "file://" + root.fileFor(root.frame) : ""
    cache: false
    asynchronous: true
    fillMode: Image.PreserveAspectFit
    smooth: true
  }
  Text {
    anchors.centerIn: parent
    visible: root.frame === 0
    text: root.failed ? "podgląd niedostępny" : "podgląd…"
    color: Theme.dim
    font.family: Theme.font
    font.pixelSize: Theme.body
  }
}
