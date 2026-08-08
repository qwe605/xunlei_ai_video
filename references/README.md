# Open-source reference repositories

Initial repositories were fetched on 2026-07-28 using shallow clones. Subtitle
alignment references were added on 2026-08-08.

## Direct reuse candidates

These repositories may be used as dependencies or as references for isolated,
license-compatible components. Preserve upstream notices when code is reused.

| Repository | Local path | Commit | Intended use |
|---|---|---|---|
| wassim249/YT-Navigator | `direct/YT-Navigator` | `61e3ddf` | Hybrid retrieval, video chunk model, timestamp search |
| SYSTRAN/faster-whisper | `direct/faster-whisper` | `ed9a06c` | Speech-to-text |
| m-bain/whisperX | `direct/whisperX` | `2cfd7b7` | Word-level timestamps and diarization |
| jianfch/stable-ts | `direct/stable-ts` | `e312072` | Waveform-based silence suppression and timestamp regrouping |
| Breakthrough/PySceneDetect | `direct/PySceneDetect` | `bba97f5` | Scene-change candidates |
| FlagOpen/FlagEmbedding | `direct/FlagEmbedding` | `7ed43d6` | Chinese/multilingual embedding and reranking |
| pgvector/pgvector | `direct/pgvector` | `721fcf4` | Vector storage in PostgreSQL |
| sampotts/plyr | `direct/plyr` | `6520022` | Web video player |
| FFmpeg/FFmpeg | `direct/FFmpeg` | `fe95359` | Media probing, extraction, and transcoding |

## Architecture references only

Do not copy GPL/AGPL source, brand assets, or UI styles into the submission.
NVIDIA VSS and Qwen3-VL are sparse checkouts to avoid unrelated large assets.

| Repository | Local path | Commit | Intended reference |
|---|---|---|---|
| immich-app/immich | `architecture/immich` | `8cb5bf9` | Smart search UX and background indexing |
| jellyfin/jellyfin | `architecture/jellyfin` | `5b55051` | Media-library domain model and playback integration |
| jxxghp/MoviePilot | `architecture/MoviePilot` | `bdf395f` | Metadata recognition, scraping, and organization stages |
| NVIDIA-AI-Blueprints/video-search-and-summarization | `architecture/video-search-and-summarization` | `7640d91` | Long-video chunking, search, Q&A, and clip retrieval |
| QwenLM/Qwen3-VL | `architecture/Qwen3-VL` | `9658872` | Optional multimodal video understanding |
| xiaoxiaomoyu/moyu-flowsub | `architecture/moyu-flowsub` | `0587832` | Qiniu training-camp realtime subtitle states and correction protocol |
| PPBrook/VoiceBridgeAI | `architecture/VoiceBridgeAI` | `f49b64d` | Qiniu training-camp WebSocket ASR pipeline; source only |

`VoiceBridgeAI` uses Git LFS for large release archives. The source tree is retained
for architecture study; the omitted `releases/VoiceBridgeAI-Local.zip` is not required
and must not be treated as a product dependency.

## Updating

Each directory is an independent Git repository. Review upstream changes and
licenses before updating; do not recursively commit these repositories into a
future product repository without choosing an explicit vendoring strategy.
