import QtQuick
import QtQuick.Layouts
import Quickshell
import "OknoModel.js" as Model
import "RetronicModel.js" as Rules

// Okno zarządzania Retronic (spec wtyczka-paska/specs/2026-10-19-retronic-okno.md, faza F2): osobny proces Quickshella
// (`quickshell -p <repo>/okno/`, patrz ../okno.sh), niezależny od paska i powłoki Omarchy. Okno tylko czyta JSON z ../okno_api.py
// i woła skrypty bota; własnej logiki bota nie ma. Układ: pasek boczny 260 px + sekcja (Ratunek, Mapa i tryb) + stopka.
ShellRoot {
  id: shell

  Backend { id: ctl }

  FloatingWindow {
    id: win
    title: "Retronic · okno zarządzania"
    // rozmiar: domyślnie jak makieta (1280x820); RETRONIC_OKNO_ROZMIAR=WxH tylko do testów układu
    readonly property var size: (Quickshell.env("RETRONIC_OKNO_ROZMIAR") || "1280x820").split("x")
    implicitWidth: Number(size[0])
    implicitHeight: Number(size[1])
    minimumSize: Qt.size(1000, 600)
    color: Theme.bg
    visible: true

    // zamknięcie okna kończy proces (jedno okno = jeden proces; okno.sh startuje go od nowa)
    onClosed: Qt.quit()
    onVisibleChanged: if (!visible) Qt.quit()

    Rectangle {
      id: root
      objectName: "okno-korzen"
      anchors.fill: parent
      color: Theme.bg

      ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---------- pasek tytułu (makieta: .titlebar)
        Rectangle {
          Layout.fillWidth: true
          Layout.preferredHeight: 34
          color: Theme.bg2
          Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.line }
          Row {
            anchors.left: parent.left
            anchors.leftMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10
            Text { text: "Retronic"; color: Theme.fg; font.family: Theme.font; font.pixelSize: Theme.small + 1; font.bold: true }
            Text { text: "okno zarządzania"; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.small + 1 }
          }
          Text {
            objectName: "tytul-prawy"
            anchors.right: parent.right
            anchors.rightMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            visible: text !== ""
            text: ctl.ratunekData ? "ratunek: cień (Haiku " + Model.counters(ctl.ratunekData).haiku + ")" : ""
            color: Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.small + 1
          }
        }

        RowLayout {
          Layout.fillWidth: true
          Layout.fillHeight: true
          spacing: 0

          Sidebar {
            Layout.preferredWidth: 260
            Layout.fillHeight: true
            ctl: ctl
          }

          Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Text {
              anchors.centerIn: parent
              visible: !ctl.loaded
              text: ctl.stanError !== "" ? "błąd odczytu stanu: " + ctl.stanError : "odczyt stanu botów…"
              color: ctl.stanError !== "" ? Theme.bad : Theme.dim
              font.family: Theme.font
              font.pixelSize: Theme.body
            }

            RatunekView {
              objectName: "widok-ratunek"
              anchors.fill: parent
              visible: ctl.loaded && ctl.section === "ratunek"
              ctl: ctl
            }
            MapaView {
              objectName: "widok-mapa"
              anchors.fill: parent
              visible: ctl.loaded && ctl.section === "mapa"
              ctl: ctl
            }
          }
        }

        // ---------- stopka: stan botów i czas odświeżenia
        Rectangle {
          Layout.fillWidth: true
          Layout.preferredHeight: 30
          color: Theme.bg2
          Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: Theme.line }

          Row {
            id: footLeft
            anchors.left: parent.left
            anchors.leftMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            spacing: 16
            Row {
              spacing: 6
              Rectangle {
                width: 9; height: 9; radius: 4.5
                anchors.verticalCenter: parent.verticalCenter
                color: Model.runningCount(ctl.instances, ctl.statuses) > 0 ? Theme.ok : Theme.dim2
              }
              Text {
                objectName: "stopka-liczba"
                text: {
                  var n = Model.runningCount(ctl.instances, ctl.statuses)
                  return n === 0 ? "żaden bot nie działa" : n + " " + Model.pluralBots(n)
                }
                color: Theme.dim
                font.family: Theme.font
                font.pixelSize: Theme.small
              }
            }
            Text {
              objectName: "stopka-boty"
              width: Math.max(0, root.width - 260 - 14 - 190)
              text: Model.footerSummary(ctl.instances, ctl.statuses, Rules.stateLabel)
              color: Theme.dim
              font.family: Theme.font
              font.pixelSize: Theme.small
              elide: Text.ElideRight
            }
          }
          Text {
            objectName: "stopka-czas"
            anchors.right: parent.right
            anchors.rightMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            text: ctl.stanError !== "" ? "błąd odczytu: " + ctl.stanError
                  : (ctl.refreshedAt ? "odświeżono " + Model.clock(ctl.refreshedAt) + " · co 2 s" : "odczyt…")
            color: ctl.stanError !== "" ? Theme.bad : Theme.dim
            font.family: Theme.font
            font.pixelSize: Theme.small
          }
        }
      }
    }

    // Scenariusz testowy (tylko gdy ustawiony RETRONIC_OKNO_SCENARIUSZ): kroki, zrzuty, kliknięcia przez tryClick().
    Scenariusz {
      ctl: ctl
      target: root
    }
  }
}
