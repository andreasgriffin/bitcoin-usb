# A python usb wrapper around hwi

* This provides an abstraction layer ontop of hwi, such that only bdk is needed from the outside
* Currently supported are
  * Coldcard


* It also provides 
  * AddressTypes, which are the commonly used bitcoin output descriptor templates
  * seed_tools.derive_spk_provider  to derive xpubs from seeds for all AddressTypes  (bdk does not support multisig templates currently https://github.com/bitcoindevkit/bdk/issues/1020)


### Demo

Run the demo with

```
python demo.py
```


### Tests

Run tests

```
python -m pytest -vvv  --log-cli-level=0
```



# Install package



### From pypi

```shell
pip install bitcoin_usb
```



###  From git

```shell
python setup.py sdist bdist_wheel
pip install .
```





# Licences

The *bitcoin_qrreader*  folder is under the [GPL3](LICENSE).

The folder *ur* is from https://github.com/Foundation-Devices/foundation-ur-py  and under   [BSD-2-Clause Plus Patent License](ur/LICENSE).

The folder *urtypes* from https://github.com/selfcustody/urtypes  is under  [MIT](urtypes/LICENSE.md).
