"""Selekcja instancji do próbnego wdrożenia; odczyt tylko przy reloadzie rdzen.

Brak manifestu oznacza zwykłe działanie nowej wersji. Instalator przed podmianą
rdzen tworzy .ai/cpu-wdrozenie.json z pustą listą, następnie wybiera jedną instancję.
Nie zmienia częstotliwości odczytów ani ustawień gry.
"""
import json
import os
from pathlib import Path
import re
import warnings


def konfiguracja(id_=None, plik=None):
    """Jeden odczyt, jeden zwalidowany snapshot dla wszystkich komponentów."""
    id_ = os.environ.get('RETRONIC_ID', '') if id_ is None else id_
    plik = Path(plik) if plik is not None else Path(__file__).resolve().parent / '.ai/cpu-wdrozenie.json'
    try:
        try:
            data = json.loads(plik.read_bytes())
        except FileNotFoundError:
            return frozenset(('scan','pid','chat'))
        ids = data['instances']
        components = data.get('components', ['scan', 'pid', 'chat'])
        if (type(data.get('schema')) is not int or data['schema'] != 1 or not isinstance(ids, list)
                or any(not isinstance(v, str) or not re.fullmatch(r'(?:[a-z0-9][a-z0-9_-]{0,23})?', v)
                       for v in ids)):
            raise ValueError('wymagane schema=1 i instances=[identyfikatory instancji]')
        if (not isinstance(components, list)
                or any(v not in ('scan','pid','chat') for v in components)):
            raise ValueError('components musi być listą scan/pid/chat')
        return frozenset(components) if id_ in ids else frozenset()
    except (OSError, ValueError, TypeError, KeyError) as e:
        warnings.warn(f'Niepoprawny manifest CPU; optymalizacje wyłączone: {e}', RuntimeWarning)
        return frozenset()


def wlaczone(id_=None, plik=None, komponent=None):
    components = konfiguracja(id_, plik)
    return bool(components) if komponent is None else komponent in components
