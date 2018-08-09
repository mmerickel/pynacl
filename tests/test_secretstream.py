# Copyright 2013-2018 Donald Stufft and individual contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import, division, print_function

import random

import pytest

import six

from nacl._sodium import ffi
from nacl.bindings.crypto_secretstream import (
    crypto_secretstream_xchacha20poly1305_ABYTES,
    crypto_secretstream_xchacha20poly1305_HEADERBYTES,
    crypto_secretstream_xchacha20poly1305_KEYBYTES,
    crypto_secretstream_xchacha20poly1305_STATEBYTES,
    crypto_secretstream_xchacha20poly1305_TAG_FINAL,
    crypto_secretstream_xchacha20poly1305_TAG_MESSAGE,
    crypto_secretstream_xchacha20poly1305_TAG_PUSH,
    crypto_secretstream_xchacha20poly1305_TAG_REKEY,
    crypto_secretstream_xchacha20poly1305_init_pull,
    crypto_secretstream_xchacha20poly1305_init_push,
    crypto_secretstream_xchacha20poly1305_keygen,
    crypto_secretstream_xchacha20poly1305_pull,
    crypto_secretstream_xchacha20poly1305_push,
    crypto_secretstream_xchacha20poly1305_rekey,
)
from nacl.utils import random as randombytes


def test_it_like_libsodium():
    ad_len = random.randint(1, 100)
    m1_len = random.randint(1, 1000)
    m2_len = random.randint(1, 1000)
    m3_len = random.randint(1, 1000)

    ad = randombytes(ad_len)
    m1 = randombytes(m1_len)
    m2 = randombytes(m2_len)
    m3 = randombytes(m3_len)
    m1_ = m1[:]
    m2_ = m2[:]
    m3_ = m3[:]

    k = crypto_secretstream_xchacha20poly1305_keygen()
    assert len(k) == crypto_secretstream_xchacha20poly1305_KEYBYTES

    # push

    state, header = crypto_secretstream_xchacha20poly1305_init_push(k)
    assert len(state) == crypto_secretstream_xchacha20poly1305_STATEBYTES
    assert len(header) == crypto_secretstream_xchacha20poly1305_HEADERBYTES

    c1 = crypto_secretstream_xchacha20poly1305_push(state, m1)
    assert len(c1) == m1_len + crypto_secretstream_xchacha20poly1305_ABYTES

    c2 = crypto_secretstream_xchacha20poly1305_push(state, m2, ad)
    assert len(c2) == m2_len + crypto_secretstream_xchacha20poly1305_ABYTES

    c3 = crypto_secretstream_xchacha20poly1305_push(
        state, m3, ad=ad, tag=crypto_secretstream_xchacha20poly1305_TAG_FINAL)
    assert len(c3) == m3_len + crypto_secretstream_xchacha20poly1305_ABYTES

    # pull

    state = crypto_secretstream_xchacha20poly1305_init_pull(header, k)

    m1, tag = crypto_secretstream_xchacha20poly1305_pull(state, c1)
    assert tag == crypto_secretstream_xchacha20poly1305_TAG_MESSAGE
    assert m1 == m1_

    m2, tag = crypto_secretstream_xchacha20poly1305_pull(state, c2, ad)
    assert tag == crypto_secretstream_xchacha20poly1305_TAG_MESSAGE
    assert m2 == m2_

    with pytest.raises(RuntimeError) as excinfo:
        crypto_secretstream_xchacha20poly1305_pull(state, c3)
    assert str(excinfo.value) == 'Unexpected failure'
    m3, tag = crypto_secretstream_xchacha20poly1305_pull(state, c3, ad)
    assert tag == crypto_secretstream_xchacha20poly1305_TAG_FINAL
    assert m3 == m3_

    # previous with FINAL tag

    with pytest.raises(RuntimeError) as excinfo:
        crypto_secretstream_xchacha20poly1305_pull(state, c3, ad)
    assert str(excinfo.value) == 'Unexpected failure'

    # previous without a tag

    with pytest.raises(RuntimeError) as excinfo:
        crypto_secretstream_xchacha20poly1305_pull(state, c2, None)
    assert str(excinfo.value) == 'Unexpected failure'

    # short ciphertext

    with pytest.raises(ValueError) as excinfo:
        c2len = random.randint(1, crypto_secretstream_xchacha20poly1305_ABYTES)
        crypto_secretstream_xchacha20poly1305_pull(state, c2[:c2len])
    assert str(excinfo.value) == 'Ciphertext is too short'
    with pytest.raises(ValueError) as excinfo:
        crypto_secretstream_xchacha20poly1305_pull(state, b'')
    assert str(excinfo.value) == 'Ciphertext is too short'

    # empty ciphertext

    with pytest.raises(ValueError) as excinfo:
        crypto_secretstream_xchacha20poly1305_pull(
            state,
            c2[:crypto_secretstream_xchacha20poly1305_ABYTES],
            None,
        )
    assert str(excinfo.value) == 'Ciphertext is too short'

    # without explicit rekeying

    state, header = crypto_secretstream_xchacha20poly1305_init_push(k)
    c1 = crypto_secretstream_xchacha20poly1305_push(state, m1)
    c2 = crypto_secretstream_xchacha20poly1305_push(state, m2)

    state = crypto_secretstream_xchacha20poly1305_init_pull(header, k)
    m1, tag = crypto_secretstream_xchacha20poly1305_pull(state, c1)
    assert m1 == m1_
    m2, tag = crypto_secretstream_xchacha20poly1305_pull(state, c2)
    assert m2 == m2_

    # with explicit rekeying

    state, header = crypto_secretstream_xchacha20poly1305_init_push(k)
    c1 = crypto_secretstream_xchacha20poly1305_push(state, m1)

    crypto_secretstream_xchacha20poly1305_rekey(state)

    c2 = crypto_secretstream_xchacha20poly1305_push(state, m2)

    state = crypto_secretstream_xchacha20poly1305_init_pull(header, k)
    m1, tag = crypto_secretstream_xchacha20poly1305_pull(state, c1)
    assert m1 == m1_

    with pytest.raises(RuntimeError):
        crypto_secretstream_xchacha20poly1305_pull(state, c2)

    crypto_secretstream_xchacha20poly1305_rekey(state)

    m2, tag = crypto_secretstream_xchacha20poly1305_pull(state, c2)
    assert m2 == m2_

    # with explicit rekeying using TAG_REKEY

    state, header = crypto_secretstream_xchacha20poly1305_init_push(k)

    state_save = ffi.buffer(state)[:]

    c1 = crypto_secretstream_xchacha20poly1305_push(
        state, m1, tag=crypto_secretstream_xchacha20poly1305_TAG_REKEY)

    c2 = crypto_secretstream_xchacha20poly1305_push(state, m2)

    csave = c2[:]

    state = crypto_secretstream_xchacha20poly1305_init_pull(header, k)
    m1, tag = crypto_secretstream_xchacha20poly1305_pull(state, c1)
    assert m1 == m1_
    assert tag == crypto_secretstream_xchacha20poly1305_TAG_REKEY

    m2, tag = crypto_secretstream_xchacha20poly1305_pull(state, c2)
    assert m2 == m2_
    assert tag == crypto_secretstream_xchacha20poly1305_TAG_MESSAGE

    # avoid using from_buffer until at least cffi >= 1.10 in setup.py
    # state = ffi.from_buffer(state_save)
    for i in range(crypto_secretstream_xchacha20poly1305_STATEBYTES):
        state[i] = six.indexbytes(state_save, i)

    c1 = crypto_secretstream_xchacha20poly1305_push(state, m1)

    c2 = crypto_secretstream_xchacha20poly1305_push(state, m2)
    assert csave != c2

    # New stream

    state, header = crypto_secretstream_xchacha20poly1305_init_push(k)

    c1 = crypto_secretstream_xchacha20poly1305_push(
        state, m1, tag=crypto_secretstream_xchacha20poly1305_TAG_PUSH)
    assert len(c1) == m1_len + crypto_secretstream_xchacha20poly1305_ABYTES

    # snip tests that require introspection into the state buffer
    # to test the nonce as we're using an opaque pointer


def test_max_message_size(monkeypatch):
    import nacl.bindings.crypto_secretstream as css
    # we want to create an oversized message but don't want to blow out
    # memory so knock it down a bit for this test
    monkeypatch.setattr(
        css,
        'crypto_secretstream_xchacha20poly1305_MESSAGEBYTES_MAX',
        2**10 - 1,
    )
    m = b'0' * (css.crypto_secretstream_xchacha20poly1305_MESSAGEBYTES_MAX + 1)
    k = crypto_secretstream_xchacha20poly1305_keygen()
    state, header = crypto_secretstream_xchacha20poly1305_init_push(k)
    with pytest.raises(ValueError) as excinfo:
        crypto_secretstream_xchacha20poly1305_push(state, m, None, 0)
    assert str(excinfo.value) == 'Message is too long'
