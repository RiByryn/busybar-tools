# Publish new version of the package to PyPI:

- Check everything
- Increment version in `pyproject.toml`
- Commit all the changes and push to GitHub

    . ./venv/bin/activate
    python -m pip install --upgrade pip build twine

    rm -rf dist build *.egg-info

    python -m build
    python -m twine check dist/*
    python -m twine upload dist/*