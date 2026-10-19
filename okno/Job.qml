import QtQuick
import Quickshell.Io

// Jedno asynchroniczne wywołanie danego rodzaju naraz (nie blokuje UI): `start(cmd, tag)` odrzuca się, gdy poprzednie jeszcze trwa.
// Wynik trafia do `finished(text, tag)`; po przekroczeniu czasu proces jest przerywany, a `finished` dostaje `timeoutText`.
QtObject {
  id: job

  property int timeoutMs: 8000
  property string timeoutText: ""
  property bool pending: false
  property string tag: ""

  signal finished(string text, string tag)

  function start(command, newTag) {
    if (pending || !command) return false
    tag = newTag === undefined ? "" : newTag
    proc.command = command
    pending = true
    timeout.restart()
    proc.running = true
    return true
  }

  function done(text) {
    if (!pending) return
    pending = false
    timeout.stop()
    fallback.stop()
    finished(text, tag)
  }

  property Process proc: Process {
    stdout: StdioCollector {
      id: out
      waitForEnd: true
      onStreamFinished: job.done(text)
    }
    // Proces, który nie wystartował, nie zamyka strumienia: po jego wyjściu domykamy sami.
    onExited: job.fallback.restart()
  }

  property Timer fallback: Timer {
    interval: 400
    onTriggered: job.done(out.text)
  }

  property Timer timeout: Timer {
    interval: job.timeoutMs
    onTriggered: {
      job.proc.running = false
      job.done(job.timeoutText)
    }
  }
}
