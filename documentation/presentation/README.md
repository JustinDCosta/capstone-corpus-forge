# Group Presentation — Corpus Forge

A single combined presentation for the three of us (Justin, Krishna, Piotr).
Built in plain HTML / CSS / JavaScript so editing slides is just text editing.

## How to run

Just double-click `group_presentation.html`, or open it in any browser:

```
open group_presentation.html       # macOS
start group_presentation.html      # Windows
xdg-open group_presentation.html   # Linux
```

No build step, no dependencies, no server.

## Controls

| Key                              | Action                          |
|----------------------------------|---------------------------------|
| `→` / `Space` / `PageDown`       | Next slide                      |
| `←` / `PageUp`                   | Previous slide                  |
| `Home` / `End`                   | First / last slide              |
| `F`                              | Toggle fullscreen               |
| `O`                              | Toggle overview grid            |
| `Esc`                            | Close overview                  |
| Click left/right edge of screen  | Navigate                        |
| Swipe (touch)                    | Navigate                        |

The URL updates as you navigate (e.g. `…/group_presentation.html#7`),
so you can bookmark or share a specific slide.

## Slide list & speaker mapping

The deck is one combined group presentation. Each slide has a
`data-speaker` attribute so the speaker tag in the top-right shows
who's up. You can re-assign speakers by editing those attributes
directly in the HTML.

| #  | Slide                          | Speaker  |
|----|--------------------------------|----------|
| 1  | Title                          | Group    |
| 2  | Agenda                         | Piotr    |
| 3  | Mission                        | Piotr    |
| 4  | Live Demo (3 min)              | Group    |
| 5  | Architecture                   | Justin   |
| 6  | Tech Stack                     | Justin   |
| 7  | Core Features (Layer 1)        | Krishna  |
| 8  | Ingestion Pipeline             | Krishna  |
| 9  | Engineering Decisions          | Justin   |
| 10 | Challenge B — Prompt Engineering | Piotr  |
| 11 | Challenge D — Reliability      | Krishna  |
| 12 | AI Collaboration               | Piotr    |
| 13 | When AI Was Wrong              | Piotr    |
| 14 | Cost Observability             | Justin   |
| 15 | Failures & Iterations          | Krishna  |
| 16 | Lessons Learned                | Group    |
| 17 | Q&A / Thank You                | Group    |

Total ≈ 17 slides for a 12-minute group presentation +
3-minute demo + 5-minute Q&A (matches the brief's 20-minute slot).

## Adding images

Put images in this folder (or a subfolder), then reference them in
the HTML wherever you want:

```html
<img src="images/architecture.png" alt="System architecture" />
```

A good place to add screenshots: slide 4 (demo) and slide 5 (architecture).

## Exporting to PDF

The deck has a `@media print` block. To save as PDF:

1. Open the HTML in Chrome / Edge.
2. `Ctrl/Cmd + P` → Destination: "Save as PDF".
3. Set Layout to **Landscape** and Margins to **None**.
4. Save as `group_presentation.pdf` in the same folder.

The HTML version is the source of truth — edit there and re-export.
