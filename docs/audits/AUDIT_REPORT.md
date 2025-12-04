# GoodQ Codebase Audit Report
**Generated**: 1760288056.2087364
**Files scanned**: 113
**Issues found**: 291

---

## Summary by Issue Type

- **Returns True without validation (could be premature)**: 158 occurrences
- **Code marked for fixing**: 120 occurrences
- **Function ellipsis (not implemented)**: 5 occurrences
- **Bare except with pass - swallows all errors**: 3 occurrences
- **Exception returns empty dict without logging**: 2 occurrences
- **Exception returns empty list without logging**: 2 occurrences
- **Exception returns None without logging**: 1 occurrences

---

## Detailed Findings

### `_archive\old_scripts_20251010_195649\file_watchdog.py`
**Issues found**: 4

**Line 194**: Code marked for fixing
```python
# TODO: Implement image-only pipeline
```

**Line 200**: Code marked for fixing
```python
# TODO: Implement audio-only pipeline
```

**Line 206**: Code marked for fixing
```python
# TODO: Implement document processing
```

**Line 212**: Code marked for fixing
```python
# TODO: Implement data file processing
```

---

### `_archive\old_scripts_20251010_195649\update_all_paths.py`
**Issues found**: 1

**Line 55**: Returns True without validation (could be premature)
```python
return True
```

---

### `api\main.py`
**Issues found**: 1

**Line 74**: Returns True without validation (could be premature)
```python
return True
```

---

### `lib\knowledge_graph.py`
**Issues found**: 1

**Line 475**: Code marked for fixing
```python
# TODO: Implement pattern matching logic
```

---

### `scripts\audit_codebase.py`
**Issues found**: 8

**Line 13**: Bare except with pass - swallows all errors
```python
1. Silent exception handling (except: pass)
```

**Line 44**: Bare except with pass - swallows all errors
```python
# Check for bare except: pass
```

**Line 52**: Bare except with pass - swallows all errors
```python
"pattern": "except: pass"
```

**Line 59**: Exception returns None without logging
```python
pattern = "except: return None"
```

**Line 62**: Exception returns empty dict without logging
```python
pattern = "except: return {}"
```

**Line 64**: Exception returns empty list without logging
```python
pattern = "except: return []"
```

**Line 72**: Exception returns empty dict without logging
```python
pattern = "except: return {}"
```

**Line 74**: Exception returns empty list without logging
```python
pattern = "except: return []"
```

---

### `scripts\cache_readiness_check.py`
**Issues found**: 2

**Line 53**: Returns True without validation (could be premature)
```python
return True
```

**Line 55**: Returns True without validation (could be premature)
```python
return True
```

---

### `scripts\comprehensive_code_audit.py`
**Issues found**: 1

**Line 34**: Code marked for fixing
```python
# TODO/FIXME/HACK comments
```

---

### `scripts\dataset_specs.py`
**Issues found**: 1

**Line 175**: Returns True without validation (could be premature)
```python
return True
```

---

### `scripts\quick_test_storage.py`
**Issues found**: 1

**Line 171**: Returns True without validation (could be premature)
```python
return True
```

---

### `scripts\validate_models.py`
**Issues found**: 8

**Line 35**: Returns True without validation (could be premature)
```python
return True
```

**Line 60**: Returns True without validation (could be premature)
```python
return True
```

**Line 87**: Returns True without validation (could be premature)
```python
return True
```

**Line 116**: Returns True without validation (could be premature)
```python
return True
```

**Line 141**: Returns True without validation (could be premature)
```python
return True
```

**Line 162**: Returns True without validation (could be premature)
```python
return True
```

**Line 183**: Returns True without validation (could be premature)
```python
return True
```

**Line 202**: Returns True without validation (could be premature)
```python
return True
```

---

### `scripts\watchdog_ingest.py`
**Issues found**: 4

**Line 382**: Returns True without validation (could be premature)
```python
return True
```

**Line 416**: Code marked for fixing
```python
# TODO: Implement audio ingestion
```

**Line 422**: Code marked for fixing
```python
# TODO: Implement image ingestion
```

**Line 428**: Code marked for fixing
```python
# TODO: Implement document ingestion
```

---

### `steps\audio_emotion\step.py`
**Issues found**: 1

**Line 29**: Returns True without validation (could be premature)
```python
return True
```

---

### `steps\common\memory_writer.py`
**Issues found**: 3

**Line 64**: Returns True without validation (could be premature)
```python
return True
```

**Line 96**: Returns True without validation (could be premature)
```python
return True
```

**Line 188**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\charset_normalizer\legacy.py`
**Issues found**: 1

**Line 9**: Code marked for fixing
```python
# TODO: remove this check when dropping Python 3.7 support
```

---

### `vendor\charset_normalizer\md.py`
**Issues found**: 5

**Line 147**: Returns True without validation (could be premature)
```python
return True
```

**Line 268**: Returns True without validation (could be premature)
```python
return True
```

**Line 419**: Returns True without validation (could be premature)
```python
return True
```

**Line 516**: Returns True without validation (could be premature)
```python
return True
```

**Line 579**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\charset_normalizer\utils.py`
**Issues found**: 4

**Line 84**: Returns True without validation (could be premature)
```python
return True
```

**Line 99**: Returns True without validation (could be premature)
```python
return True
```

**Line 122**: Returns True without validation (could be premature)
```python
return True
```

**Line 220**: Code marked for fixing
```python
and character != "\ufeff"  # bug discovered in Python,
```

---

### `vendor\colorama\ansitowin32.py`
**Issues found**: 2

**Line 53**: Returns True without validation (could be premature)
```python
return True
```

**Line 69**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\colorama\tests\utils.py`
**Issues found**: 1

**Line 10**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\colorama\winterm.py`
**Issues found**: 1

**Line 192**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\fsspec\asyn.py`
**Issues found**: 5

**Line 199**: Returns True without validation (could be premature)
```python
return True
```

**Line 334**: Code marked for fixing
```python
# TODO: implement on_error
```

**Line 498**: Code marked for fixing
```python
# TODO: on_error
```

**Line 696**: Returns True without validation (could be premature)
```python
return True
```

**Line 985**: Code marked for fixing
```python
# TODO: readahead might still be useful here, but needs async version
```

---

### `vendor\fsspec\caching.py`
**Issues found**: 2

**Line 93**: Code marked for fixing
```python
# TODO: use rich for better formatting
```

**Line 501**: Code marked for fixing
```python
# TODO: only set start/end after fetch, in case it fails?
```

---

### `vendor\fsspec\compression.py`
**Issues found**: 2

**Line 13**: Code marked for fixing
```python
# TODO: files should also be available as contexts
```

**Line 125**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\fsspec\dircache.py`
**Issues found**: 1

**Line 73**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\fsspec\generic.py`
**Issues found**: 2

**Line 326**: Code marked for fixing
```python
# TODO: special case for one FS being local, which can use get/put
```

**Line 327**: Code marked for fixing
```python
# TODO: special case for one being memFS, which can use cat/pipe
```

---

### `vendor\fsspec\implementations\arrow.py`
**Issues found**: 1

**Line 99**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\fsspec\implementations\cache_metadata.py`
**Issues found**: 1

**Line 159**: Code marked for fixing
```python
# TODO: consolidate blocks here
```

---

### `vendor\fsspec\implementations\cached.py`
**Issues found**: 2

**Line 323**: Code marked for fixing
```python
# TODO: action where partial file exists in read-only cache
```

**Line 510**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\fsspec\implementations\dbfs.py`
**Issues found**: 1

**Line 477**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\fsspec\implementations\ftp.py`
**Issues found**: 1

**Line 349**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\fsspec\implementations\http.py`
**Issues found**: 2

**Line 104**: Code marked for fixing
```python
# TODO: Maybe rename `self.kwargs` to `self.request_options` to make
```

**Line 349**: Code marked for fixing
```python
autocommit=None,  # XXX: This differs from the base class.
```

---

### `vendor\fsspec\implementations\http_sync.py`
**Issues found**: 4

**Line 105**: Code marked for fixing
```python
# TODO: encoding from headers
```

**Line 484**: Code marked for fixing
```python
autocommit=None,  # XXX: This differs from the base class.
```

**Line 883**: Code marked for fixing
```python
# TODO: not allowed in JS
```

**Line 896**: Code marked for fixing
```python
# TODO:
```

---

### `vendor\fsspec\implementations\local.py`
**Issues found**: 4

**Line 292**: Returns True without validation (could be premature)
```python
return True
```

**Line 356**: Code marked for fixing
```python
# TODO: if all incoming paths were posix-compliant then separator would
```

**Line 397**: Code marked for fixing
```python
# TODO: check if path is writable?
```

**Line 460**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\fsspec\implementations\reference.py`
**Issues found**: 7

**Line 147**: Code marked for fixing
```python
# TODO: derive fs from `root`
```

**Line 473**: Code marked for fixing
```python
# TODO: only save needed columns
```

**Line 546**: Code marked for fixing
```python
# TODO: only clear those that we wrote to?
```

**Line 578**: Returns True without validation (could be premature)
```python
return True
```

**Line 748**: Code marked for fixing
```python
# TODO: warning here, since this can be very expensive?
```

**Line 884**: Code marked for fixing
```python
# TODO: if references is lazy, pre-fetch all paths in batch before access
```

**Line 985**: Code marked for fixing
```python
# TODO: we make dircache by iterating over all entries, but for Spec >= 1,
```

---

### `vendor\fsspec\implementations\smb.py`
**Issues found**: 1

**Line 394**: Code marked for fixing
```python
# TODO: use transaction support in SMB protocol
```

---

### `vendor\fsspec\implementations\tar.py`
**Issues found**: 3

**Line 78**: Code marked for fixing
```python
# TODO: tarfile already implements compression with modes like "'r:gz'",
```

**Line 92**: Code marked for fixing
```python
# TODO: load and set saved index, if exists
```

**Line 101**: Code marked for fixing
```python
# TODO: save index to self.index_store here, if set
```

---

### `vendor\fsspec\implementations\webhdfs.py`
**Issues found**: 1

**Line 443**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\fsspec\spec.py`
**Issues found**: 3

**Line 493**: Code marked for fixing
```python
# TODO: allow equivalent of -name parameter
```

**Line 661**: Returns True without validation (could be premature)
```python
return True
```

**Line 1956**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\fsspec\tests\abstract\__init__.py`
**Issues found**: 1

**Line 285**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\fsspec\utils.py`
**Issues found**: 2

**Line 223**: Returns True without validation (could be premature)
```python
return True
```

**Line 300**: Code marked for fixing
```python
# TODO: allow length to be None and read to the end of the file?
```

---

### `vendor\huggingface_hub\_commit_api.py`
**Issues found**: 1

**Line 789**: Code marked for fixing
```python
# TODO: (optimization) download regular files to copy concurrently
```

---

### `vendor\huggingface_hub\_local_folder.py`
**Issues found**: 1

**Line 386**: Code marked for fixing
```python
# TODO: can we do better?
```

---

### `vendor\huggingface_hub\_oauth.py`
**Issues found**: 1

**Line 155**: Code marked for fixing
```python
# TODO: handle generic case (handling OAuth in a non-Space environment with custom dev values) (low priority)
```

---

### `vendor\huggingface_hub\_upload_large_folder.py`
**Issues found**: 1

**Line 695**: Code marked for fixing
```python
# Hacks with CommitOperationAdd to bypass checks/sha256 calculation
```

---

### `vendor\huggingface_hub\cli\cache.py`
**Issues found**: 1

**Line 355**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\huggingface_hub\cli\jobs.py`
**Issues found**: 2

**Line 356**: Returns True without validation (could be premature)
```python
return True
```

**Line 842**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\huggingface_hub\commands\delete_cache.py`
**Issues found**: 3

**Line 85**: Code marked for fixing
```python
# TODO: refactor this + imports in a unified pattern across codebase
```

**Line 233**: Code marked for fixing
```python
# Hacky way to dynamically set an instruction message to the checkbox when
```

**Line 387**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\huggingface_hub\dataclasses.py`
**Issues found**: 3

**Line 210**: Code marked for fixing
```python
# Hack to be able to raise if `.validate()` already exists except if it was created by this decorator on a parent class
```

**Line 432**: Code marked for fixing
```python
# Hacky: we cannot use a lambda here because of reference issues
```

**Line 464**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\huggingface_hub\hf_api.py`
**Issues found**: 10

**Line 338**: Code marked for fixing
```python
def __post_init__(self):  # hack to make LastCommitInfo backward compatible
```

**Line 348**: Code marked for fixing
```python
def __post_init__(self):  # hack to make BlobLfsInfo backward compatible
```

**Line 359**: Code marked for fixing
```python
def __post_init__(self):  # hack to make BlogSecurityInfo backward compatible
```

**Line 371**: Code marked for fixing
```python
def __post_init__(self):  # hack to make TransformersInfo backward compatible
```

**Line 380**: Code marked for fixing
```python
def __post_init__(self):  # hack to make SafeTensorsInfo backward compatible
```

**Line 2911**: Returns True without validation (could be premature)
```python
return True
```

**Line 2958**: Returns True without validation (could be premature)
```python
return True
```

**Line 3016**: Returns True without validation (could be premature)
```python
return True
```

**Line 4746**: Code marked for fixing
```python
# TODO: remove this in v1.0
```

**Line 5019**: Code marked for fixing
```python
# TODO: remove this in v1.0
```

---

### `vendor\huggingface_hub\hf_file_system.py`
**Issues found**: 3

**Line 327**: Code marked for fixing
```python
# TODO: use `commit_description` to list all the deleted paths?
```

**Line 713**: Code marked for fixing
```python
"tree_id": None,  # TODO: tree_id of the root directory?
```

**Line 795**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\huggingface_hub\hub_mixin.py`
**Issues found**: 2

**Line 349**: Returns True without validation (could be premature)
```python
return True
```

**Line 351**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\huggingface_hub\inference\_client.py`
**Issues found**: 1

**Line 255**: Code marked for fixing
```python
# TODO: this should be handled in provider helpers directly
```

---

### `vendor\huggingface_hub\inference\_common.py`
**Issues found**: 1

**Line 434**: Code marked for fixing
```python
# Hacky way to retrieve payload in case of aiohttp error
```

---

### `vendor\huggingface_hub\inference\_generated\_async_client.py`
**Issues found**: 1

**Line 253**: Code marked for fixing
```python
# TODO: this should be handled in provider helpers directly
```

---

### `vendor\huggingface_hub\inference\_generated\types\base.py`
**Issues found**: 2

**Line 145**: Code marked for fixing
```python
# Hacky way to keep dataclass values in sync when dict is updated
```

**Line 152**: Code marked for fixing
```python
# Hacky way to keep dict values is sync when dataclass is updated
```

---

### `vendor\huggingface_hub\inference\_mcp\cli.py`
**Issues found**: 1

**Line 39**: Code marked for fixing
```python
_patch_anyio_open_process()  # Hacky way to prevent stdio connections to be stopped by Ctrl+C
```

---

### `vendor\huggingface_hub\inference\_mcp\mcp_client.py`
**Issues found**: 3

**Line 118**: Function ellipsis (not implemented)
```python
async def add_mcp_server(self, type: Literal["stdio"], **params: Unpack[StdioServerParameters_T]): ...
```

**Line 121**: Function ellipsis (not implemented)
```python
async def add_mcp_server(self, type: Literal["sse"], **params: Unpack[SSEServerParameters_T]): ...
```

**Line 124**: Function ellipsis (not implemented)
```python
async def add_mcp_server(self, type: Literal["http"], **params: Unpack[StreamableHTTPParameters_T]): ...
```

---

### `vendor\huggingface_hub\keras_mixin.py`
**Issues found**: 2

**Line 45**: Code marked for fixing
```python
if not hasattr(model, "history"):  # hacky way to check if model is Keras 2.x
```

**Line 494**: Code marked for fixing
```python
# TODO: change this in a future PR. We are not returning a KerasModelHubMixin instance here...
```

---

### `vendor\huggingface_hub\repocard_data.py`
**Issues found**: 3

**Line 157**: Returns True without validation (could be premature)
```python
return True
```

**Line 466**: Code marked for fixing
```python
# TODO - maybe handle this similarly to EvalResult?
```

**Line 752**: Code marked for fixing
```python
# TODO - Check if there cases where this list is longer than one?
```

---

### `vendor\huggingface_hub\repository.py`
**Issues found**: 3

**Line 238**: Returns True without validation (could be premature)
```python
return True
```

**Line 280**: Returns True without validation (could be premature)
```python
return True
```

**Line 1245**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\huggingface_hub\serialization\_torch.py`
**Issues found**: 3

**Line 121**: Code marked for fixing
```python
>>> from huggingface_hub import load_torch_model  # TODO
```

**Line 811**: Returns True without validation (could be premature)
```python
return True
```

**Line 814**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\huggingface_hub\utils\_hf_folder.py`
**Issues found**: 3

**Line 25**: Code marked for fixing
```python
# TODO: deprecate when adapted in transformers/datasets/gradio
```

**Line 43**: Code marked for fixing
```python
# TODO: deprecate when adapted in transformers/datasets/gradio
```

**Line 58**: Code marked for fixing
```python
# TODO: deprecate when adapted in transformers/datasets/gradio
```

---

### `vendor\huggingface_hub\utils\_runtime.py`
**Issues found**: 1

**Line 226**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\huggingface_hub\utils\_typing.py`
**Issues found**: 3

**Line 63**: Returns True without validation (could be premature)
```python
return True
```

**Line 72**: Returns True without validation (could be premature)
```python
return True
```

**Line 86**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\huggingface_hub\utils\_validators.py`
**Issues found**: 1

**Line 91**: Code marked for fixing
```python
# TODO: add an argument to opt-out validation for specific argument?
```

---

### `vendor\huggingface_hub\utils\tqdm.py`
**Issues found**: 2

**Line 188**: Returns True without validation (could be premature)
```python
return True
```

**Line 208**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\idna\core.py`
**Issues found**: 12

**Line 61**: Returns True without validation (could be premature)
```python
return True
```

**Line 67**: Returns True without validation (could be premature)
```python
return True
```

**Line 81**: Returns True without validation (could be premature)
```python
return True
```

**Line 137**: Returns True without validation (could be premature)
```python
return True
```

**Line 143**: Returns True without validation (could be premature)
```python
return True
```

**Line 151**: Returns True without validation (could be premature)
```python
return True
```

**Line 165**: Returns True without validation (could be premature)
```python
return True
```

**Line 196**: Returns True without validation (could be premature)
```python
return True
```

**Line 209**: Returns True without validation (could be premature)
```python
return True
```

**Line 227**: Returns True without validation (could be premature)
```python
return True
```

**Line 234**: Returns True without validation (could be premature)
```python
return True
```

**Line 240**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\idna\intranges.py`
**Issues found**: 2

**Line 51**: Returns True without validation (could be premature)
```python
return True
```

**Line 56**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\packaging\_manylinux.py`
**Issues found**: 3

**Line 189**: Returns True without validation (could be premature)
```python
return True
```

**Line 194**: Returns True without validation (could be premature)
```python
return True
```

**Line 204**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\packaging\_structures.py`
**Issues found**: 4

**Line 23**: Returns True without validation (could be premature)
```python
return True
```

**Line 26**: Returns True without validation (could be premature)
```python
return True
```

**Line 43**: Returns True without validation (could be premature)
```python
return True
```

**Line 46**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\packaging\_tokenizer.py`
**Issues found**: 1

**Line 135**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\packaging\metadata.py`
**Issues found**: 2

**Line 204**: Code marked for fixing
```python
# TODO: The spec doesn't say anything about if the keys should be
```

**Line 805**: Code marked for fixing
```python
description: _Validator[str | None] = _Validator()  # TODO 2.1: can be in body
```

---

### `vendor\packaging\requirements.py`
**Issues found**: 2

**Line 29**: Code marked for fixing
```python
# TODO: Can we test whether something is contained within a requirement?
```

**Line 32**: Code marked for fixing
```python
# TODO: Can we normalize the name and extra name?
```

---

### `vendor\packaging\specifiers.py`
**Issues found**: 3

**Line 268**: Returns True without validation (could be premature)
```python
return True
```

**Line 465**: Returns True without validation (could be premature)
```python
return True
```

**Line 495**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\packaging\tags.py`
**Issues found**: 1

**Line 378**: Code marked for fixing
```python
# TODO: Need to care about 32-bit PPC for ppc64 through 10.2?
```

---

### `vendor\requests\_internal_utils.py`
**Issues found**: 1

**Line 48**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\requests\adapters.py`
**Issues found**: 1

**Line 663**: Code marked for fixing
```python
# TODO: Remove this in 3.0.0: see #2811
```

---

### `vendor\requests\auth.py`
**Issues found**: 3

**Line 181**: Code marked for fixing
```python
# XXX not implemented yet
```

**Line 215**: Code marked for fixing
```python
# XXX handle auth-int.
```

**Line 220**: Code marked for fixing
```python
# XXX should the partial digests be encoded too?
```

---

### `vendor\requests\cookies.py`
**Issues found**: 3

**Line 70**: Returns True without validation (could be premature)
```python
return True
```

**Line 302**: Returns True without validation (could be premature)
```python
return True
```

**Line 325**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\requests\hooks.py`
**Issues found**: 1

**Line 19**: Code marked for fixing
```python
# TODO: response is the only one
```

---

### `vendor\requests\models.py`
**Issues found**: 2

**Line 225**: Returns True without validation (could be premature)
```python
return True
```

**Line 767**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\requests\sessions.py`
**Issues found**: 1

**Line 132**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\requests\utils.py`
**Issues found**: 9

**Line 107**: Returns True without validation (could be premature)
```python
return True
```

**Line 112**: Returns True without validation (could be premature)
```python
return True
```

**Line 706**: Returns True without validation (could be premature)
```python
return True
```

**Line 730**: Returns True without validation (could be premature)
```python
return True
```

**Line 776**: Returns True without validation (could be premature)
```python
return True
```

**Line 787**: Returns True without validation (could be premature)
```python
return True
```

**Line 791**: Returns True without validation (could be premature)
```python
return True
```

**Line 801**: Returns True without validation (could be premature)
```python
return True
```

**Line 811**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\tqdm\__init__.py`
**Issues found**: 3

**Line 3**: Code marked for fixing
```python
from .cli import main  # TODO: remove in v5.0.0
```

**Line 4**: Code marked for fixing
```python
from .gui import tqdm as tqdm_gui  # TODO: remove in v5.0.0
```

**Line 5**: Code marked for fixing
```python
from .gui import trange as tgrange  # TODO: remove in v5.0.0
```

---

### `vendor\tqdm\cli.py`
**Issues found**: 2

**Line 30**: Returns True without validation (could be premature)
```python
return True
```

**Line 117**: Code marked for fixing
```python
# TODO: add custom support for some of the following?
```

---

### `vendor\tqdm\gui.py`
**Issues found**: 1

**Line 26**: Code marked for fixing
```python
# TODO: @classmethod: write() on GUI?
```

---

### `vendor\tqdm\keras.py`
**Issues found**: 3

**Line 114**: Returns True without validation (could be premature)
```python
return True
```

**Line 118**: Returns True without validation (could be premature)
```python
return True
```

**Line 122**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\tqdm\notebook.py`
**Issues found**: 1

**Line 175**: Code marked for fixing
```python
# Hack-ish way to avoid the danger bar_style being overridden by
```

---

### `vendor\tqdm\rich.py`
**Issues found**: 1

**Line 74**: Code marked for fixing
```python
# TODO: @classmethod: write()?
```

---

### `vendor\tqdm\std.py`
**Issues found**: 4

**Line 1263**: Returns True without validation (could be premature)
```python
return True
```

**Line 1350**: Returns True without validation (could be premature)
```python
return True
```

**Line 1442**: Code marked for fixing
```python
# TODO: private method
```

**Line 1498**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\tqdm\tk.py`
**Issues found**: 2

**Line 31**: Code marked for fixing
```python
# TODO: @classmethod: write()?
```

**Line 184**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\tqdm\utils.py`
**Issues found**: 3

**Line 9**: Code marked for fixing
```python
# TODO consider using wcswidth third-party package for 0-width characters
```

**Line 263**: Returns True without validation (could be premature)
```python
return True
```

**Line 278**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\typing_extensions.py`
**Issues found**: 12

**Line 734**: Returns True without validation (could be premature)
```python
return True
```

**Line 745**: Returns True without validation (could be premature)
```python
return True
```

**Line 750**: Code marked for fixing
```python
# Hack so that typing.Generic.__class_getitem__
```

**Line 754**: Returns True without validation (could be premature)
```python
return True
```

**Line 786**: Returns True without validation (could be premature)
```python
return True
```

**Line 826**: Function ellipsis (not implemented)
```python
def close(self): ...
```

**Line 1518**: Returns True without validation (could be premature)
```python
return True
```

**Line 1928**: Code marked for fixing
```python
# Hack to get typing._type_check to pass.
```

**Line 1971**: Code marked for fixing
```python
# Hack to get typing._type_check to pass in Generic.
```

**Line 2104**: Code marked for fixing
```python
# Hack: Arguments must be types, replace it with one.
```

**Line 2470**: Function ellipsis (not implemented)
```python
def foo(**kwargs: Unpack[Movie]): ...
```

**Line 3319**: Code marked for fixing
```python
# TODO: Use inspect.VALUE here, and make the annotations lazily evaluated
```

---

### `vendor\urllib3\_base_connection.py`
**Issues found**: 1

**Line 20**: Code marked for fixing
```python
# TODO: Remove this in favor of a better
```

---

### `vendor\urllib3\connection.py`
**Issues found**: 2

**Line 330**: Code marked for fixing
```python
# TODO: Fix tunnel so it doesn't depend on self.sock state.
```

**Line 561**: Code marked for fixing
```python
# TODO should we implement it everywhere?
```

---

### `vendor\urllib3\connectionpool.py`
**Issues found**: 3

**Line 576**: Returns True without validation (could be premature)
```python
return True
```

**Line 578**: Code marked for fixing
```python
# TODO: Add optional support for socket.gethostbyname checking.
```

**Line 1095**: Code marked for fixing
```python
# TODO revise this, see https://github.com/urllib3/urllib3/issues/2791
```

---

### `vendor\urllib3\contrib\emscripten\connection.py`
**Issues found**: 1

**Line 149**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\urllib3\contrib\emscripten\fetch.py`
**Issues found**: 4

**Line 151**: Returns True without validation (could be premature)
```python
return True
```

**Line 370**: Returns True without validation (could be premature)
```python
return True
```

**Line 392**: Returns True without validation (could be premature)
```python
return True
```

**Line 726**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\urllib3\exceptions.py`
**Issues found**: 1

**Line 306**: Code marked for fixing
```python
# TODO(t-8ch): Stop inheriting from AssertionError in v2.0.
```

---

### `vendor\urllib3\http2\__init__.py`
**Issues found**: 1

**Line 38**: Code marked for fixing
```python
# TODO: Offer 'http/1.1' as well, but for testing purposes this is handy.
```

---

### `vendor\urllib3\http2\connection.py`
**Issues found**: 5

**Line 144**: Code marked for fixing
```python
# TODO SKIPPABLE_HEADERS from urllib3 are ignored.
```

**Line 234**: Code marked for fixing
```python
# TODO: Arbitrary read value.
```

**Line 282**: Code marked for fixing
```python
# TODO this is often present from upstream.
```

**Line 325**: Code marked for fixing
```python
# TODO: This is a woefully incomplete response object, but works for non-streaming.
```

**Line 332**: Code marked for fixing
```python
decode_content: bool = False,  # TODO: support decoding
```

---

### `vendor\urllib3\response.py`
**Issues found**: 8

**Line 782**: Code marked for fixing
```python
# FIXME: Ideally we'd like to include the url in the ReadTimeoutError but
```

**Line 787**: Code marked for fixing
```python
# FIXME: Is there a better way to differentiate between SSLErrors?
```

**Line 1005**: Code marked for fixing
```python
# TODO make sure to initially read enough data to get past the headers
```

**Line 1051**: Code marked for fixing
```python
# FIXME, this method's type doesn't say returning None is possible
```

**Line 1098**: Returns True without validation (could be premature)
```python
return True
```

**Line 1126**: Returns True without validation (could be premature)
```python
return True
```

**Line 1132**: Returns True without validation (could be premature)
```python
return True
```

**Line 1219**: Code marked for fixing
```python
# FIXME: Rewrite this method and make it a class with a better structured logic.
```

---

### `vendor\urllib3\util\proxy.py`
**Issues found**: 1

**Line 43**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\urllib3\util\response.py`
**Issues found**: 1

**Line 99**: Code marked for fixing
```python
# FIXME: Can we do this somehow without accessing private httplib _method?
```

---

### `vendor\urllib3\util\retry.py`
**Issues found**: 3

**Line 339**: Returns True without validation (could be premature)
```python
return True
```

**Line 385**: Returns True without validation (could be premature)
```python
return True
```

**Line 400**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\urllib3\util\ssl_.py`
**Issues found**: 1

**Line 503**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\urllib3\util\url.py`
**Issues found**: 1

**Line 454**: Code marked for fixing
```python
# TODO: Remove this when we break backwards compatibility.
```

---

### `vendor\urllib3\util\wait.py`
**Issues found**: 1

**Line 92**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\yaml\__init__.py`
**Issues found**: 1

**Line 21**: Code marked for fixing
```python
# XXX "Warnings control" is now deprecated. Leaving in the API function to not
```

---

### `vendor\yaml\emitter.py`
**Issues found**: 1

**Line 122**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\yaml\parser.py`
**Issues found**: 2

**Line 101**: Returns True without validation (could be premature)
```python
return True
```

**Line 104**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\yaml\representer.py`
**Issues found**: 3

**Line 138**: Returns True without validation (could be premature)
```python
return True
```

**Line 140**: Returns True without validation (could be premature)
```python
return True
```

**Line 142**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\yaml\resolver.py`
**Issues found**: 1

**Line 141**: Returns True without validation (could be premature)
```python
return True
```

---

### `vendor\yaml\scanner.py`
**Issues found**: 12

**Line 119**: Returns True without validation (could be premature)
```python
return True
```

**Line 122**: Returns True without validation (could be premature)
```python
return True
```

**Line 149**: Returns True without validation (could be premature)
```python
return True
```

**Line 154**: Returns True without validation (could be premature)
```python
return True
```

**Line 187**: Code marked for fixing
```python
# TODO: support for BOM within a stream.
```

**Line 354**: Returns True without validation (could be premature)
```python
return True
```

**Line 688**: Returns True without validation (could be premature)
```python
return True
```

**Line 696**: Returns True without validation (could be premature)
```python
return True
```

**Line 704**: Returns True without validation (could be premature)
```python
return True
```

**Line 715**: Returns True without validation (could be premature)
```python
return True
```

**Line 725**: Returns True without validation (could be premature)
```python
return True
```

**Line 761**: Code marked for fixing
```python
# TODO: We need to make tab handling rules more sane. A good rule is
```

---

