from setuptools import find_packages, setup, Extension

requirements = []

setup(
    packages=find_packages(exclude=["docs"]),
    python_requires=">=3.6",
    install_requires=requirements,
    ext_modules=[Extension("plum.function", ["plum/function.py"])],
    include_package_data=True,
)
