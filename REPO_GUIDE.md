# REPO GUIDE — Schema-UML

A structured overview of the repository for developers to navigate, understand, and extend the project.

---

## 0) TL;DR 

**Purpose:** Interactive editor for data models, run as **Light Mode**: a pip-installable local app (single user, SQLite persistence). A static build of the same app runs entirely in the browser (GitHub Pages).
It supports schema graphing, docs/usage inspection, custom class/quantity edits, inherited member projection for `is_a` relationships, overview mode, and empty-canvas editing.

**Frontend:** React + TypeScript + Cytoscape + ELK  
**Backend:** FastAPI + SQLite + installed schema package sourcing
**Python:** 3.11 recommended/tested (package requires >=3.11).

**Main directories:**
- `web/` — frontend React app  
- `api/` — FastAPI backend  
- `api/light_mode/` — Light Mode app, schema source policy, local store, CLI  
- `extractor/` — schema graph & usage extractor  
- `scripts/` — maintenance helpers (including Light Mode static asset sync)

**Key endpoints:**
- Core: `GET /health`, `GET /workspace`, `PUT /workspace`, `GET /roots`, `GET /schema`, `GET /overview`, `GET /usage`
- Schema edits: `GET /schema/edits`, `POST /schema/edits`, `DELETE /schema/edits`, `DELETE /schema/edits/{id}`
- Schema versioning/update: `GET /schema/version`, `POST /schema/update`
- Submission: `POST /send-design`
- `GET /git/packages` lists the schema's modules, with the profile's fixed branch.

Shared query flags for `/schema` and related graph endpoints: `include_quantities`, `include_subsections`, `include_inheritance`, `allow_cross_module`, `base_namespace`, `root`, and `empty` (empty-canvas mode).

**Essential env (optional):**
~~~bash
# optional endpoint for "Send design"
export SCHEMA_STUDIO_SEND_ENDPOINT=https://your-endpoint.example/api
# optional frontend override
export SCHEMA_STUDIO_DIST_DIR=/abs/path/to/web/dist
# optional: disable first-run auto bootstrap (default enabled)
export SCHEMA_STUDIO_AUTO_BOOTSTRAP_SCHEMA=0
~~~
`Send Design` UI is shown only when `SCHEMA_STUDIO_SEND_ENDPOINT` is set.

**Start it quickly:** `pip install -e . && schema-studio`

**UX highlights:**
- UML cards show **sections**; **quantities** appear as attributes inside the card (not separate nodes).
- Right **Doc Panel** shows the **class docstring** and a **clickable list of quantities**; clicking a quantity shows its docstring.
- Right **Audit trail** panel tracks edit history, archive/restore state, and export/reset actions.
- Left sidebar **Under-the-hood** panel shows **normalization methods and helper functions** that act on the selected section (based on `/usage`).
- **Editable mode**: add classes (inheritance or subsection links) and add/rename/remove quantities; dtype validated against allowlist; custom classes get fully qualified ids so quantities work immediately.
- New classes linked with `inherits` (`is_a`) automatically surface inherited quantities/subsections in the UML and doc panels.
- Inherited quantities are read-only on child classes (edit/remove/redefine is blocked).
- **Bird’s-eye overview** renders packages/classes without building the full graph.
- **Overlays**: inheritance defaults on; dtype/shape labels toggleable.
- Workspace includes **Show base sections** (default off) to hide/show framework/base hierarchy in the canvas.
- **Exports**: download the current graph JSON or a PDF snapshot.
- **Empty canvas**: start from `<base>.custom_schema`, edit freely, and reset its stored edits when needed (UI calls `DELETE /schema/edits`). Its edits apply to the whole profile's schema, so new classes can build on existing ones.

**Edit model (important for agents):**
- An edit is an operation on the LinkML schema (`api/sources/edits.py`): add, rename or remove a class or attribute, set range, description or required, add or remove enum values. Each stored edit records profile, module, the schema commit it was made on, target and payload.
- Edits are stored per profile in local SQLite (single user), each under the module of the class it changes (a new class: the module it is added to). An older database format is recreated, not migrated. The static site keeps them in `localStorage`.
- The backend replays all of the profile's stored edits, in order, onto the freshly converted LinkML schema of the module's snapshot, then builds the graph from that (`api/sources/editing.py`); a class shows the same edits in every module that draws it. The module's own edits that no longer apply, or that applied over a change in the schema source, are reported in `edit_conflicts`.
- `POST /schema/edits` builds the resulting graph before it stores anything, so an error stores nothing, and stores its edits all or none (one SQLite transaction). `DELETE /schema/edits` deletes a list of edit ids and, if a module is named, that module's edits, in one transaction.
- Which edits a profile allows comes from the profile (`edit_rules`): NOMAD dtypes for both NOMAD profiles, openBIS data types and codes for bam-masterdata. Inherited members are edited on the class that declares them.
- Frontend audit trail is UI history; each entry keeps the ids of the edits it stored, and undo deletes them (the entry stays if that fails). Clear deletes the current module's edits and those its entries made.

**API compatibility headers:**
- Frontend sends `X-Schema-UML-Version` and `X-Schema-UML-Features` so backends can gate behavior across different schema repos.

**Typing/normalization helpers (frontend):**
- `src/types/api.ts` enforces runtime parsing of graph payloads.
- `src/utils/identifier.ts` normalizes ids/labels/fqids used across GraphView, DocPanel, and selection store.
- `src/utils/umlState.ts` builds effective UML state (including inherited quantities/subsections) from backend graph payloads.
- `src/utils/errors.ts` standardizes API error formatting.

**Workspace state:**
- Stored in `src/store/workspace.ts` (branch/pkg/base namespace/startEmpty), synced with backend `/workspace` and persisted locally for reloads.
- The branch is fixed per profile by backend policy.

**Contract tests:**
- `npm run test:run` (from `web/`) executes frontend UI flows + contract parsing/identifier checks using Vitest + happy-dom.
- `npm run test:contracts` runs only the contract/identifier subset.
- New classes: `add_class` gives id `{package}.{name}` (bam-masterdata: the name follows from the object type code); a subsection link is a second edit, `add_attribute` with kind `subsection` on the parent.
- New quantities: `add_attribute` on the class id; they get the annotations extracted ones have, so the graph shows them the same way.
- A quantity cannot redefine an inherited one on a child class (server validation).
- `POST /schema/edits` stores a list of edits all or none; the graph it returns already holds them.

---

## 1) Repository Structure

~~~text
schema-studio/
├─ api/                         # FastAPI backend
│  ├─ light_mode/               # Light Mode backend
│  │  ├─ app.py                 # Light Mode API (no auth, fixed-branch policy, send-design)
│  │  ├─ schema_source.py       # Installed schema package sourcing + /schema/update policy
│  │  ├─ store.py               # Local SQLite workspace/custom edit store
│  │  ├─ cli.py                 # `schema-studio` entrypoint
│  │  └─ tests/                 # Light Mode backend tests
│  ├─ sources/                  # Snapshots, LinkML conversion, graph adapter and schema edits
│  │  ├─ core.py                # Edits replayed onto a snapshot; graph, roots, usage, YAML (stdlib only)
│  │  ├─ browser.py             # The static site's requests to the core (runs in Pyodide)
│  │  └─ editing.py             # The server's side: finds snapshots, legacy path
│
├─ extractor/
│  ├─ graph_builder.py          # build_graph(package, **opts); embeds docstrings
│  ├─ scripts/usage_index.py    # get_usage_for_section(section_qualname) for /usage
│
├─ web/                         # React frontend (Vite)
│  ├─ src/
│  │  ├─ App.tsx                # Sidebar, API calls, overview, export
│  │  ├─ client.ts              # The one place requests go out: HTTP, or the static backend
│  │  ├─ static/                # Static site: backend in the browser, edit store, Pyodide worker
│  │  ├─ GraphView.tsx          # Cytoscape UML renderer (sections only; quantities folded)
│  │  ├─ components/
│  │  │  ├─ DocPanel.tsx        # Class/quantity docstrings; quantity list (clickable)
│  │  │  ├─ OverviewGrid.tsx    # Bird’s-eye view of packages and classes
│  │  │  └─ UnderTheHoodPanel.tsx # Shows normalize methods/helpers for selected section
│  │  ├─ store/
│  │  │  └─ selection.ts        # Zustand store for selected item (class or quantity)
│  │  ├─ utils/
│  │  │  └─ umlState.ts         # Effective UML state with inherited quantities/subsections
│  │  └─ index.css
│  ├─ index.html
│  └─ package.json
│
├─ scripts/build_snapshots.py   # Snapshot files of every profile for builds without environments
├─ .github/workflows/pages.yml  # Builds and publishes the static site (GitHub Pages)
├─ README.md                    # Quick start, features, troubleshooting
└─ REPO_GUIDE.md                
~~~

---

## 2) Data Contracts

### 2.1 Graph JSON (`GET /schema` → consumed by frontend)

Example (shortened):

~~~json
{
  "package": "nomad_simulations.schema_packages.model_method",
  "root": "ModelMethod",
  "nodes": [
    {
      "id": "nomad_simulations.schema_packages.model_method.ModelMethod",
      "kind": "section",
      "label": "ModelMethod",
      "module": "nomad_simulations.schema_packages.model_method",
      "doc": "Section docstring here...",
      "methods": ["normalize", "validate"]
    },
    {
      "id": "nomad_simulations.schema_packages.model_method.ModelMethod.determinant",
      "kind": "quantity",
      "label": "determinant",
      "owner": "nomad_simulations.schema_packages.model_method.ModelMethod",
      "dtype": "Enum(restricted, unrestricted, restricted-open-shell)",
      "shape": null,
      "card": null,
      "doc": "The spin-coupling form of the determinant used for ..."
    }
  ],
  "edges": [
    {
      "source": "nomad_simulations.schema_packages.model_method.ModelMethod",
      "target": "nomad_simulations.schema_packages.model_method.BasisSetContainer",
      "type": "hasSubSection",
      "card": "0..*"
    }
  ]
}
~~~

**Notes**

- `kind ∈ {"section","quantity"}`.  
- Quantities include `doc`; optional source metadata (`path`, `line`) may be present and is shown by the frontend when available.  
- The frontend does not render quantity nodes on the canvas; it folds them into each section’s card and into the Doc Panel.  
- Section `id` is always a fully qualified class name, e.g. `nomad_simulations.schema_packages.model_method.DFT`.

### 2.2 Usage JSON (`GET /usage` → used by Under-the-hood panel)

~~~json
{
  "usage": [
    {
      "kind": "normalize_method",
      "qualname": "nomad.datamodel.data.Section.normalize",
      "module": "nomad.datamodel.data",
      "short_name": "normalize",
      "doc": "Is called during entry normalization."
    },
    {
      "kind": "normalize_function",
      "qualname": "nomad_simulations.schema_packages.model_method.normalize_dft",
      "module": "nomad_simulations.schema_packages.model_method",
      "short_name": "normalize_dft",
      "doc": "Normalize DFT-related fields for the DFT section."
    }
  ],
  "workspace": {
    "branch": "develop",
    "package": "nomad_simulations.schema_packages.model_method",
    "base_namespace": "nomad_simulations.schema_packages"
  }
}
~~~

**Notes**

- Request: `GET /usage?section_id=<fully-qualified-section-class-name>`
  Example: `section_id=nomad_simulations.schema_packages.model_method.DFT`
- Response elements:
  - `kind`: `"normalize_method"`, `"normalize_function"`, or `"utility_function"`.  
  - `qualname`: fully-qualified Python name of the callable.  
  - `module`: module where the callable is defined.  
  - `short_name`: simple function/method name, e.g. `normalize_dft`.  
  - `doc`: first-paragraph summary of the callable’s docstring (shortened).  

The frontend shows these entries as a list under **Under the hood** for the currently selected section.

### 2.3 Edit request (`POST /schema/edits`)

~~~json
{
  "package": "nomad_simulations.schema_packages.model_method",
  "edits": [
    {
      "op": "add_attribute",
      "target": "nomad_simulations.schema_packages.model_method.ModelMethod",
      "payload": {"name": "my_quantity", "kind": "quantity", "dtype": "float64", "description": "Optional"}
    }
  ]
}
~~~

**Notes**

- The edits are checked against the profile's rules and the current (edited) schema, then stored with the schema commit; the response is the module's graph with `persisted_edits`, `applied_edits` and, if any, `edit_conflicts`.
- The allowed dtypes come from the profile (`edit_rules` in `GET /schema/profiles`, or `GET /schema/edits`).

---

## 3) Backend Flow

### `api/light_mode/app.py`

1. **Schema source policy (`GET /schema/version`, `POST /schema/update`)**
   - Always uses installed `nomad-simulations` package.
   - Update path pulls latest remote `develop` lineage via pip.
   - Local repo indicators are ignored by policy.

2. **Workspace (`GET /workspace`, `PUT /workspace`)**
   - Single user local workspace in SQLite.
   - Branch is enforced to `develop`; non-`develop` requests are rejected.

3. **`GET /schema`, `GET /roots`**
   - Builds graph from installed package modules.
   - Replays persisted local edits from SQLite.

4. **Schema edits (`GET`/`POST`/`DELETE /schema/edits`, `DELETE /schema/edits/{id}`)**
   - Stored locally in SQLite.
   - Inherited-quantity redefinition on child classes is rejected.

5. **`GET /overview`, `GET /usage`**
   - Overview and under-the-hood data from installed package imports/introspection.

6. **`GET /git/packages`**
   - Lists the schema's modules, with the profile's fixed branch.

**Key files**

- `api/light_mode/app.py` — Light Mode API, fixed branch policy, send-design endpoint.
- `api/light_mode/schema_source.py` — installed package policy + update behavior.
- `api/light_mode/store.py` — SQLite workspace/custom edit persistence.
- `extractor/graph_builder.py` — embeds graph structure + docstrings for sections and quantities.
- `extractor/scripts/usage_index.py` — introspects normalize methods and helpers; exposes `get_usage_for_section`.

---

## 4) Frontend Flow

- **`App.tsx`**
  - Sidebar includes **Under the hood** (usage inspection via `/usage`).
  - **Build graph:** `/schema`.
  - **Bird’s-eye view:** calls `/overview` and renders an `OverviewGrid` of packages/classes.
  - **Exports:** JSON download and PDF snapshot (via `GraphView` export handle).
  - Right column:
    - Top: `DocPanel` (schema docs + quantities, includes inline edit/remove hooks).
    - Bottom: audit trail (edit history, archive/restore, clear).
  - **Editable mode:** toggles whether class/quantity mutation actions are enabled; every addition, rename, change and removal is stored through `/schema/edits`.
  - Workspace controls include **Show base sections** (default off): off keeps diagrams focused on selected schema namespace; on restores full base/framework hierarchy.
  - Every request goes through `client.ts` (`createApiClient`, `apiFetch`); no component calls `fetch` or Axios directly.
  - Static site:
    - Compile-time: `VITE_STATIC_MODE=true` (the GitHub Pages build, `npm run build:pages`); `client.ts` then answers every request with `static/backend.ts`, which reads the site's snapshot files (`data/index.json`) and runs `api/sources/core.py` in Pyodide in a web worker (`static/worker.ts`). Edits are kept in `localStorage` (`static/editStore.ts`).

- **`GraphView.tsx`**
  - Renders sections as UML cards using Cytoscape + ELK.
  - Applies namespace-based class filtering when **Show base sections** is off; base/framework sections are hidden unless explicitly shown.
  - Keeps session-added classes visible/selectable in filtered view (so newly created classes can be edited immediately).
  - Folds quantity metadata into each section’s card label (attributes) and into a `quantitiesByOwner` map for the Doc Panel.
  - Mouse-wheel zoom sensitivity is intentionally damped for finer control.
  - On node tap:
    - Builds a `Selected` object with:
      - `id = fully-qualified section name`.
      - `kind = "class"`.
      - `name`, `doc`, `path`, `line`.
      - `quantities` for that section.
    - Calls `useSelection.getState().setSelected(...)`.
  - Styles: composition edges (diamonds), inheritance edges (dashed, hollow arrow).
  - Exposes `toPng()` via `GraphExportHandle` for PDF export in the sidebar.

- **`components/DocPanel.tsx`**
  - Reads `selected` from `useSelection`.
  - For a selected class:
    - Shows class name + docstring.
    - Lists quantities (name + dtype/shape/card); clicking a quantity displays its docstring.
    - Provides inline edit/remove controls when editable mode is on.
  - For a selected quantity:
    - Shows that quantity’s docstring and type info.
    - Shows inherited-from metadata when applicable.
    - Inherited quantities remain read-only in editable mode.

- **`components/UnderTheHoodPanel.tsx`**
  - Props: `{ apiBase: string, methods?: string[] }`.  
  - Reads `selected` from `useSelection`.  
  - If a class is selected:
    - Calls `GET {apiBase}/usage?section_id=<selected.id>`.  
    - Renders a list of:
      - `Section.normalize()` implementations (`kind="normalize_method"`).  
      - Module-level helpers (`kind="normalize_function"`).  
    - Shows `short_name`, module, and a short doc summary for each entry.  
  - If nothing or a quantity is selected: shows a placeholder.

- **`components/AddQuantityForm.tsx` & `components/QuantityEditPanel.tsx`**
  - Form helpers for editable mode (add/rename/remove quantities with validation messaging).
  - Enforce read-only behavior for inherited quantities in the UI.

- **`store/selection.ts`**
  - Zustand store with:
    - `selected: Selected | null`
    - `setSelected(s: Selected | null)`
  - `Selected` holds:
    - `id`, `kind`, `name`, `doc`, `path`, `line`
    - inherited quantity metadata (`inherited`, `inheritedFromId`, `inheritedFromName`, `sourceId`) when kind is quantity
    - optional `quantities` (for class nodes).

**Performance tips**

- For large modules, disable cross-module traversal and/or subsections to keep the graph small.
- Bird’s-eye view (`OverviewGrid`) is a cheap way to spot new/removed classes without rendering a full graph.
- Keep **Show base sections** off for cleaner, lower-noise UML views in large inheritance trees.

---

## 5) Common Contributor Operations

**Add/change graph building**

- Edit `extractor/graph_builder.py`.  
- Function signature:

  ~~~python
  build_graph(
      package: str,
      root: str | None = None,
      include_quantities: bool = True,
      include_subsections: bool = True,
      include_inheritance: bool = True,
      allow_cross_module: bool = True,
      base_namespace: str | None = None,
  ) -> dict:
      ...
  ~~~  
- Ensure quantities include `doc` (and any optional metadata expected by frontend contracts).

**Extend usage / normalization discovery**

- Edit `extractor/scripts/usage_index.py`.  
  - Add new heuristics for `"utility_function"` or additional normalize helpers.  
  - Keep the `UsageEntry` dataclass and `/usage` response model in sync with the frontend.

**Add endpoints**

- Add handlers in `api/light_mode/app.py`, and the matching route in `web/src/static/backend.ts` for the static site.

**Adjust diagram styles/behavior**

- Edit `web/src/GraphView.tsx` for Cytoscape styles, label formatting, layout.  
- Edit `web/src/components/DocPanel.tsx` and `web/src/components/UnderTheHoodPanel.tsx` for panel layout/content.

---

## 6) Extension Ideas

- Export PNG/SVG of the current graph (`cy.png({ full: true })`, `cy.svg({ full: true })`).  
- Search box to highlight nodes/attrs by name or dtype.  
- Show normalize source: extend `/usage` to optionally include `inspect.getsource(...)` and render it in a collapsible block.  

---

## 7) Operational Notes

**Light Mode local state**

~~~text
$SCHEMA_STUDIO_HOME/light_mode.sqlite3
# default fallback (if SCHEMA_STUDIO_HOME unset):
#   <platform user config dir>/.../light_mode.sqlite3
#   or <cwd>/.schema_studio_light/light_mode.sqlite3 (when config dir not writable)
~~~

**Light Mode schema updates**

- On startup, Light Mode attempts a one-time automatic bootstrap when schema metadata is unavailable.
- Runtime update path is `POST /schema/update` (or UI "Update schema").
- Update implementation runs `python -m pip install --upgrade git+https://github.com/nomad-coe/nomad-simulations.git@develop`, then invalidates import caches.

**Light Mode frontend assets**

- Light Mode serves bundled static assets from `api/light_mode/static` by default.
- `SCHEMA_STUDIO_DIST_DIR` can override this path (useful for local frontend iteration).
- When frontend source changes need to be shipped in Light Mode, rebuild and sync:

~~~bash
npm --prefix web run build
./scripts/sync_light_mode_static.sh
~~~

---

## 8) Known Constraints

- Very large graphs + ELK can be slow in the browser; use filters or narrow the base namespace.
- Quantities are not nodes in the canvas; they are folded into each class card.  
- Cross-module traversal can explode node count; keep a tight `base_namespace` during exploration.
