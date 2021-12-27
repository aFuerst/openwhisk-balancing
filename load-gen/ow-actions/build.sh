# rm helloPython.zip
# cp __main__.py ./venv
# cp requirements.txt ./venv
# docker build -t alfuerst/wsk-py3-pybuild -f Dockerfile.py3.7 .
# docker build -t alfuerst/wsk-pyai-pybuild -f Dockerfile.pyai .

mkdir -p ./venv
cd ./venv

# rm -rf ./venv/virtualenv

pip="python3 -m pip install --upgrade pip"
pip="$pip && python3 -c 'import sys; sys.path.append(r\"/_manylinux.py\")'"
# pip="$pip && python -c \"import platform; print(platform.architecture())\""
pip="$pip && python3 -m pip install numpy" # https://files.pythonhosted.org/packages/b3/a9/b1bc4c935ed063766bce7d3e8c7b20bd52e515ff1c732b02caacf7918e5a/numpy-1.18.5-cp36-cp36m-manylinux1_x86_64.whl
pip="$pip && python3 -m pip install pandas"
pip="$pip && python3 -m pip install pyaes"
pip="$pip && python3 -m pip install chameleon"
pip="$pip && python3 -m pip install Pillow"
pip="$pip && python3 -m pip install boto3"
pip="$pip && python3 -m pip install uuid"
pip="$pip && python3 -m pip install joblib"

# pip="$pip && pip install --no-binary :all: opencv-python-headless"

pip="$pip && pip install --upgrade https://files.pythonhosted.org/packages/ee/ff/48bde5c0f013094d729fe4b0316ba2a24774b3ff1c52d924a8a4cb04078a/six-1.15.0-py2.py3-none-any.whl"

# TODO: get CV2 / opencv working
# pip="$pip && pip install -v --upgrade https://files.pythonhosted.org/packages/72/c2/e9cf54ae5b1102020ef895866a67cb2e1aef72f16dd1fde5b5fb1495ad9c/opencv_python-4.2.0.34-cp36-cp36m-manylinux1_x86_64.whl"
# pip="$pip && pip install opencv-python"

cmd="cd tmp && virtualenv virtualenv && source virtualenv/bin/activate && python3 -m pip install -U pip"
docker run --rm -v "$PWD:/tmp" -v "$PWD/pip-cache/:/root/.cache/:rw" -e "XDG_CACHE_HOME=/root/.cache/pip/" --entrypoint /bin/bash alfuerst/action-python-v3.6-ai -c "$cmd && $pip"
docker run --rm -v "$PWD:/tmp" -v "$PWD/pip-cache/:/root/.cache/:rw" -e "XDG_CACHE_HOME=/root/.cache/pip/" --entrypoint /bin/bash alfuerst/action-python-v3.7 -c "$cmd && $pip"

# exit 0

# exclude=$(find ./virtualenv/ -wholename '*/tests/*')
# exclude_cache=$(find ./virtualenv/ -wholename '*/__pycache__/*')
# exclude_exe=$(find ./virtualenv/ -wholename '*exe')
# exclude_pip=$(find ./virtualenv/ -wholename '*/pip/*')
# exclude_setuptools=$(find ./virtualenv/ -wholename '*/setuptools/*')

for dir in ../actions/*/
do
    dir=${dir%*/}      # remove the trailing "/"
    echo ${dir##*/}    # print everything after the final "/"
    zip_cmd="zip -r ${dir##*/}.zip ./virtualenv/bin/activate_this.py "
    reqs="../actions/${dir##*/}/reqs.txt"
    # echo $reqs
    
    if [ -f $reqs ]; then
        while read p; do
            # echo $line
            if [ "$p" = "six" ]; then
                zip_cmd="$zip_cmd ./virtualenv/lib/python3.6/site-packages/six.py ./virtualenv/lib/python3.7/site-packages/six.py"
            elif [ "$p" = "opencv_python_headless" ]; then
                zip_cmd="$zip_cmd ./virtualenv/lib/python3.6/site-packages/opencv_python_headless-4.2.0.34.dist-info/"
            else
                zip_cmd="$zip_cmd ./virtualenv/lib/python3.6/site-packages/$p ./virtualenv/lib/python3.7/site-packages/$p"
            fi
            # elif [ "$p" = "uuid" ]; then
            #     zip_cmd="$zip_cmd ./virtualenv/lib/python3.6/site-packages/uuid.py ./virtualenv/lib/python3.7/site-packages/uuid.py"
            # echo $zip_cmd
        done < $reqs
    fi
    # echo "copying all py"
    # ls "../actions/${dir##*/}/"
    cp "../actions/${dir##*/}/"*.py .
    # ls .
    # echo "end results"
    # cp "../actions/${dir##*/}/"*.py .
    zip_cmd="$zip_cmd ./"*.py
    # cat "./actions/${dir##*/}/reqs.txt"
    echo $zip_cmd
    eval $zip_cmd
    cp "${dir##*/}.zip" ..
    rm *.py
done

# -x $exclude -x $exclude_cache -x $exclude_pip -x $exclude_setuptools 
# zip -r helloPython.zip ./virtualenv/bin/activate_this.py ./virtualenv/lib/python3.6/site-packages/numpy ./virtualenv/lib/python3.6/site-packages/pandas __main__.py
# zip -r helloPython.zip ./virtualenv/ __main__.py
# zip -r helloPython.zip virtualenv/bin/activate_this.py virtualenv/lib/python3.6/site-packages __main__.py &> zip.txt
# zip -r helloPython.zip virtualenv hello.py -x $exclude -x $exclude_cache -x $exclude_exe &> zip.txt
mv *.zip ../
cd ..