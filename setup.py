from setuptools import find_packages, setup

requirements = ["beartype"]

setup(
    packages=find_packages(include=["plum*"]),
    python_requires=">=3.7",
    install_requires=requirements,
    include_package_data=True,
)
