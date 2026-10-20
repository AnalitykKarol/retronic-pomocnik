# SPEC: własna tożsamość sprzętu dla instancji (`RETRONIC_ID`), 2026-10-20

Status: **approved 20.10 (D1–D4 + rozszerzenie (b)) — zaimplementowane i zweryfikowane na żywej grze `invincible` 20.10 ~12:55; `test` nadal na starych identyfikatorach do restartu.**
Dowód 20.10 12:14: `siec_proxy.sh` z TOZ_* na prefiksie w scratchpadzie: IP 152.55.184.240, `/etc/machine-id` w środku podmienione (host bez zmian), wolumen `d836-74a1`, dysk `WINEHDISK`, UUID płyty = machine-id instancji, `eth0` z MAC 00:e0:4c:…; testy `testy/test_tozsamosc.py` 5/5. Potem machine-id zmienione na UUID v4 (jak systemd) i tożsamość `test` wygenerowana na nowo.

## Cel
Instancja inna niż główna (np. `test`, Johny) ma pokazywać grze inne identyfikatory sprzętu niż Mastafian.
Główna instancja bez zmian.

## Stan zmierzony (20.10, `wine reg/vol/wmic` w prefiksie i sieci instancji)
| Identyfikator | Skąd wine go bierze | Główna vs `test` |
|---|---|---|
| MachineGuid | rejestr prefiksu | różne (świeży prefiks) |
| MAC kart | interfejsy w namespace sieci | główna: prawdziwe `enp3s0`/`wlo1`; `test`: tylko `tun0` bez MAC |
| Numer wolumenu C: | plik `drive_c/.windows-serial`, inaczej domyślne `4300-0000` | ten sam |
| Dysk (model+serial) | UDisks2 przez systemowy D-Bus (`SSDPR-CX400-512-G2-G07097558`) | ten sam |
| UUID płyty (SMBIOS) | `/sys/class/dmi/id/product_uuid` nieczytelne bez roota → `/etc/machine-id` | ten sam |
| CPU ProcessorId | instrukcja CPUID | ten sam (wspólny dla modelu CPU, nie unikalny) |

Klient składa `OTCLIENT-HARDWARE-ID-V2` z DISK, VOLUME, MACHINE, LAST-RESORT-MAC. NIEZMIERZONE: co faktycznie wysyła.

## Mechanizm (próby na prefiksie w scratchpadzie, 20.10)
- Wolumen: `drive_c/.windows-serial` (8 cyfr hex) → `vol c:` = `6d2e-91a7`. **Działa.**
- Dysk: `DBUS_SYSTEM_BUS_ADDRESS=unix:path=/nonexistent` dla procesu gry → `WINEHDISK` (generyczny, jak u każdego bez udisks). **Działa.**
- MAC: w namespace sieci `ip tuntap add dev eth0 mode tap` + `ip link set eth0 address …` → jedna karta `eth0` z naszym MAC. **Działa** (veth też, ale widać drugi koniec).
- UUID płyty: bind-mount pliku na `/etc/machine-id` w prywatnej przestrzeni montowania (`unshare -m`). **Nie sprawdzone**: polecenie zablokował klasyfikator Claude Code (zmiana widoczna tylko w namespace, system nietknięty).
- CPU: bez zmian (wymagałoby wirtualizacji); poza zakresem.

## Projekt
- `instancje/<id>/tozsamosc.json` generowany raz (losowo) i stały między startami: `volume_serial`, `mac`, `machine_id`.
- `siec_proxy.sh` (ścieżka tylko dla `RETRONIC_PROXY=1`): w namespace tworzy `eth0` (tap) z MAC instancji, ustawia `DBUS_SYSTEM_BUS_ADDRESS`, a po akcepcie D3 dodaje `-m` i bind-mount `machine-id`.
- `uruchom_gre.sh`: zapis `.windows-serial` do prefiksu instancji przed startem.
- Główna instancja: nie przechodzi przez te ścieżki.

## Decyzje Karola
- D1: MAC z prawdziwym prefiksem producenta (np. Intel/Realtek; rekomendacja) czy dowolny lokalny `02:…` (od razu widać, że sztuczny).
- D2: dysk generyczny `WINEHDISK` (rekomendacja; prosto) czy własny fałszywy numer (wymaga atrapy UDisks2 na D-Bus, dużo pracy).
- D3: zgoda na prywatny bind-mount `/etc/machine-id` w namespace instancji (inaczej UUID płyty zostaje wspólny).
- D4: czy wymusić dla `RETRONIC_ID≠""` także domyślne `RETRONIC_PROXY=1` (lekcja 20.10).

## Weryfikacja
`hwid.sh` (MachineGuid, `vol`, `wmic diskdrive/csproduct/nic`) w sieci działającej gry `test` (`nsenter -t <pid>`) vs główna:
różne wolumen, dysk, UUID, MAC; główna bez zmian; gra loguje się i chodzi przez proxy (IP ≠ domowe).

## Ryzyko
Johny już był widziany z identyfikatorami wspólnymi z Mastafianem (i z domowego IP rano 20.10). Zmiana teraz nie cofa tego,
co serwer mógł zapisać; nagła zmiana sprzętu tej samej postaci też może być sygnałem. Nie wiemy, czy serwer to porównuje.

## Cofnięcie
Usunąć `instancje/<id>/tozsamosc.json` i `drive_c/.windows-serial`; kopie skryptów `*.bak-20261020-tozsamosc`.

## Rozszerzenie 20.10 (b): stały profil instancji — decyzja Karola 20.10 ~12:50
„Każdy ma mieć stałe te dane: jedno IP, jedne części, zawsze przez proxy i z tym konfigiem konkretne konta.”
- `instancje/<id>/profil.json` (bez haseł): `proxy.host`, `proxy.port`, `proxy.user`, `ip_oczekiwane` (lista), `konto`, `postac`.
  Hasło proxy: keyring `service=retronic-proxy instance=<id>` (`haslo_proxy.sh <id>`).
- Instancja bez `profil.json` nie startuje. Start odmawia, gdy inna instancja ma ten sam endpoint proxy albo wspólne IP.
- `siec_proxy.sh` przed startem gry sprawdza w sieci instancji IP wyjściowe; spoza `ip_oczekiwane` = gra nie startuje.
- Nowa instancja `invincible`: świeży prefiks (nowy MachineGuid, klient sam tworzy `uuid`), proxy Webshare nr 5
  (`p.webshare.io:80`, login `evitnvfx-5`, IP 84.247.60.125 Lizbona; zmierzone 5/5 to samo IP, SOCKS5 i port gry 5500 OK),
  ustawienia klienta i bota od Mastafiana BEZ `uuid`, `account`, `password`, `autoReconnect`, `motd`, `recentAccounts.otml`.
  Nowe konto zakłada i loguje Karol.

## D5 (20.10 ~15:20, decyzja Karola „zrób to i zmień obecnym”): nazwa użytkownika i komputera per instancja
Klient (`RetronicGL.exe`) ma Lua `getUserName`, `getCpuId`, `getMacAddresses`, `getVolumeSerialNumber`, `getOSName`, klucz urządzenia
i wykrywanie VM. Pomiar: `USER` nie zmienia GetUserName (wine bierze nazwę z `/etc/passwd`, domenę z nazwy hosta).
- `tozsamosc.json`: `uzytkownik` (z puli zwykłych nazw, inny niż w pozostałych instancjach) i `komputer` (DESKTOP-XXXXXXX); stare pliki uzupełniane.
- `siec_proxy.sh`: prywatny bind `/etc/passwd` z tą nazwą dla naszego uida, przestrzeń UTS z nazwą hosta, `USER`/`LOGNAME` gry.
- `zmien_uzytkownika.py`: przeniesienie prefiksu `users/charlie` → `users/<nazwa>` + ścieżki w rejestrze; skróty Pulpit/Dokumenty → puste katalogi.
- CPU (CPUID, poziom modelu) i model płyty zostają wspólne: pod wine niezmienialne, VM wykrywana przez klienta. Świadomie bez zmian.
Weryfikacja na żywo 20.10 15:2x: invincible `DESKTOP-2AMKXQ4\Michal`, kutangen `DESKTOP-NPAEV9X\Pawel`, dawajkesh `DESKTOP-JHTIZEV\Kuba`.
