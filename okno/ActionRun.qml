import QtQuick

// Przebieg akcji jednej instancji (Backend.runFor): własny Job i cooldown, więc akcje różnych instancji idą równolegle.
// Skrypt, który wisi dłużej niż limit (Model.actionTimeoutMs: 25 s, sesja 120 s), jest przerywany i zgłasza RC=124 (jak na pasku).
// Blokada ok. 1,5 s po akcji (jak na pasku): drugi klik nie trafi w przycisk, który zdążył zmienić się w przeciwny.
QtObject {
  id: run

  property var owner: null          // Backend
  property string runId: ""
  property string kind: ""
  property Job job: Job {
    timeoutMs: 25000
    timeoutText: "Przekroczono czas\nRC=124"
    onFinished: function(text, tag) { run.owner.onActionFinished(text, tag, run.kind) }
  }
  property Timer cooldown: Timer {
    interval: 1500
    onTriggered: run.owner.endBusy(run.runId)
  }
}
