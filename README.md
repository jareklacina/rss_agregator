# RSS Digest Agent

Automatický agent, který třikrát denně stáhne RSS feedy, vyfiltruje relevantní články pomocí Claude AI, sumarizuje je a pošle do Telegram kanálu.

## Pipeline

1. **Cron trigger** — GitHub Actions spouští agent v 7:00, 12:00 a 18:00 CET
2. **RSS fetch** — stáhne nakonfigurované RSS feedy
3. **Deduplikace** — přeskočí články, které již byly zpracovány (Supabase)
4. **Claude filtr** — Claude Haiku rozhodne, zda je článek relevantní
5. **Stažení textu** — stáhne plný text článku (s autentizací pro placené zdroje)
6. **Sumarizace** — Claude Sonnet shrne článek do 2–3 vět
7. **Telegram** — odešle každý článek jako samostatnou zprávu

## Nastavení

### 1. Fork / clone repozitáře

```bash
git clone <url-repozitáře>
cd rss-digest-agent
```

### 2. Nastavení GitHub Secrets

V GitHub repozitáři jdi na **Settings → Secrets and variables → Actions** a přidej:

| Secret | Popis |
|--------|-------|
| `ANTHROPIC_API_KEY` | API klíč z [console.anthropic.com](https://console.anthropic.com) |
| `SUPABASE_URL` | URL Supabase projektu (např. `https://xyz.supabase.co`) |
| `SUPABASE_KEY` | Supabase `anon` klíč (z Project Settings → API) |
| `TELEGRAM_BOT_TOKEN` | Token Telegram bota (viz níže) |
| `TELEGRAM_CHAT_ID` | ID Telegram kanálu (viz níže) |
| `DENIKN_COOKIE` | Session cookie pro Deník N (viz níže) |

### 3. Supabase — vytvoření tabulky

Jdi do Supabase SQL editoru a spusť:

```sql
CREATE TABLE processed_articles (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url text UNIQUE NOT NULL,
    created_at timestamptz DEFAULT now()
);
```

RLS nech vypnuté (výchozí stav pro nové tabulky).

### 4. Telegram — vytvoření bota a kanálu

#### Vytvoření bota
1. Otevři Telegram a najdi **@BotFather**
2. Pošli `/newbot`
3. Zvol jméno bota (např. `RSS Digest Bot`)
4. Zvol username bota (musí končit na `bot`, např. `my_rss_digest_bot`)
5. BotFather ti pošle **token** — ulož ho jako `TELEGRAM_BOT_TOKEN`

#### Vytvoření kanálu a přidání bota
1. Vytvoř nový Telegram kanál (**New Channel**)
2. Nastav ho jako **Private** (nebo Public, jak chceš)
3. Přidej bota jako **Administrator** kanálu (s oprávněním posílat zprávy)

#### Zjištění Chat ID kanálu
Po přidání bota do kanálu pošli do kanálu libovolnou zprávu, pak otevři:

```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

V odpovědi najdeš `"chat":{"id": -1001234567890, ...}` — toto záporné číslo je `TELEGRAM_CHAT_ID`.

### 5. Deník N — získání cookie

1. Přihlas se na [denikn.cz](https://denikn.cz) ve svém prohlížeči
2. Otevři DevTools (F12) → záložka **Network**
3. Obnov stránku, klikni na libovolný request na denikn.cz
4. V hlavičkách requestu najdi `Cookie: ...`
5. Zkopíruj celou hodnotu a ulož jako `DENIKN_COOKIE`

Cookie expiruje — bude potřeba ji občas obnovit.

## Přidání nových RSS zdrojů

Otevři `config.yaml` a přidej řádek do sekce `feeds`:

```yaml
feeds:
  - name: "Deník N"
    url: "https://denikn.cz/feed/"
    auth: "denikn"
  - name: "Respekt"           # přidat nový zdroj
    url: "https://www.respekt.cz/rss"
    auth: "none"              # bez autentizace
```

Pro zdroj s autentizací přidej strategii do `auth_strategies`:

```yaml
auth_strategies:
  respekt:
    type: "cookie"
    env_var: "RESPEKT_COOKIE"  # a přidej odpovídající GitHub Secret
```

## Přidání nového typu zdroje (Bluesky, Reddit…)

Architektura je navržena pro snadné rozšíření:

1. Vytvoř nový modul `fetcher_bluesky.py` (nebo `fetcher_reddit.py`)
2. Implementuj funkci vracející `list[Article]`
3. Zavolej ji z `main.py` a výsledky přidej k ostatním článkům
4. Přidej konfiguraci do `config.yaml`

## Lokální spuštění

```bash
pip install -r requirements.txt

export ANTHROPIC_API_KEY=sk-ant-...
export SUPABASE_URL=https://xyz.supabase.co
export SUPABASE_KEY=eyJ...
export TELEGRAM_BOT_TOKEN=123456:ABC...
export TELEGRAM_CHAT_ID=-1001234567890
export DENIKN_COOKIE="session=abc123; ..."

python main.py
```

## Struktura projektu

```
rss-digest-agent/
├── .github/
│   └── workflows/
│       └── rss-digest.yml      # GitHub Actions workflow (cron 3x denně)
├── config.yaml                  # Konfigurace feedů, okruhů, modelů
├── main.py                      # Hlavní orchestrace pipeline
├── fetcher.py                   # RSS fetch + routing autentizace
├── deduplication.py             # Supabase deduplikace
├── relevance_filter.py          # Claude Haiku filtr relevance
├── article_reader.py            # HTTP stažení + extrakce textu z HTML
├── summarizer.py                # Claude Sonnet sumarizace
├── telegram_sender.py           # Formátování + odesílání do Telegramu
├── requirements.txt             # Python závislosti
└── README.md                    # Tato dokumentace
```
