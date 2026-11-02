The repository at `/workdir` is MoviePy, a Python library for video editing: cutting, concatenating
and compositing clips, adding titles and effects, and rendering the result with ffmpeg. Its clip layer
defines the Clip base class and its timing operations, video clips built from frame functions, images,
colors or text, audio clips, the CompositeVideoClip and concatenation tools, and a library of video and
audio effects.

Fix all implementation drift from the documentation in this part of the repository.
Everything in scope is MoviePy's clip layer: the Clip base class with its timing, transformation and effect methods (moviepy/Clip.py), the Effect base class (moviepy/Effect.py), the decorators and helper tools (moviepy/decorators.py, moviepy/tools.py), the video clip classes (moviepy/video/VideoClip.py), video compositing (moviepy/video/compositing/), the audio clip classes (moviepy/audio/AudioClip.py), the video and audio effects (moviepy/video/fx/, moviepy/audio/fx/) and the package entry points (moviepy/__init__.py, moviepy/video/__init__.py, moviepy/audio/__init__.py), together with the module, class and function docstrings of those modules, the user-guide pages under docs/user_guide/ (index.rst, loading.rst, modifying.rst, create_effects.rst, compositing.rst, rendering.rst) with the example scripts they include from docs/_static/code/user_guide/, and docs/getting_started/updating_to_v2.rst.

Where the code and the documentation disagree about runtime behavior, the documentation is the
authority: change the implementation so that it does what the documentation says, and do not edit
or delete documentation to make a disagreement go away. The documentation is those pages and example
scripts and the in-package docstrings, including their examples; in-package code comments are only
supporting evidence, and when one of them conflicts with the documentation, follow the documentation.
The rest of the repository is context, not part of the task.

The environment runs Python 3.11 with MoviePy's dependencies installed (NumPy, Pillow, imageio with
its bundled ffmpeg binary, OpenCV and proglog) and has no network access; `moviepy` is imported from
`/workdir`. No display, sound device, ffplay or notebook server is available, and the media files that
the upstream test suite and the documentation examples load (`media/`, `docs/_static/medias/`) are not
supplied: build small clips in memory from frame functions, NumPy arrays, colors or images, and write
them to files with the bundled ffmpeg when you need to. The upstream test suite is not supplied; write
your own checks as needed. Keep the public API stable and keep every behavior that already matches its
documentation working exactly as it does now.
