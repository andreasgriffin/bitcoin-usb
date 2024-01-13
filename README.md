# Wrapper around hwi, such that one can sign bdk PSBTs directly

* This provides an abstraction layer ontop of hwi, such that only bdk is needed from the outside
* Currently supported are
  * Coldcard


* It also provides 
  * AddressTypes, which are the commonly used bitcoin output descriptor templates
  * seed_tools.derive_spk_provider  to derive xpubs from seeds for all AddressTypes  (bdk does not support multisig templates currently https://github.com/bitcoindevkit/bdk/issues/1020)
  * SoftwareSigner which can sign single and multisig PSBTs, this doesn't do any security checks, so only use it on testnet


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

### Library Usage

* For xpub derivation bip_utils is used
* For signing a psbt python-bitcointx is used


# Install package



### From pypi

```shell
pip install bitcoin_usb
```



###  From git

* Install  requirements:

```shell
poetry install
```

* Automatic commit formatting

```shell
pip install pre-commit
pre-commit install
```


* Run the precommit manually for debugging

```shell
pre-commit run --all-files
```


