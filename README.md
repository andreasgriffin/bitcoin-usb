# A python usb wrapper around hwi

* This provides an abstraction layer ontop of hwi, such that only bdk is needed from the outside
* Currently supported are
  * Coldcard


### Demo

Run the demo with

```
python demo.py
```



# Install package



### From pypi

```shell
pip install bitcoin_usb
```



###  From git

```shell
python setup.py sdist bdist_wheel
pip install dist/bitcoin_qrreader*.whl  
```





# Licences

The *bitcoin_qrreader*  folder is under the [GPL3](LICENSE).

The folder *ur* is from https://github.com/Foundation-Devices/foundation-ur-py  and under   [BSD-2-Clause Plus Patent License](ur/LICENSE).

The folder *urtypes* from https://github.com/selfcustody/urtypes  is under  [MIT](urtypes/LICENSE.md).
