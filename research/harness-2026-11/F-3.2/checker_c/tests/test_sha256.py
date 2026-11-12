"""T10 (BINDING_RULE): the C SHA-256 (checker_c/sha256.h) against FIPS 180-2/NIST vectors and Python hashlib.

Builds tests/sha256_cli from sha256_cli.c (strict C99, the checker's CFLAGS) and compares:
- NIST published digests for "", "abc", the 448-bit and 896-bit two-block messages and one million 'a';
- hashlib on every length 0..200 (covers 55, 56, 63, 64, 65 and multi-block), and on random messages up to 300 KB.
Run: python3 test_sha256.py   (exit 0 on pass)."""
import hashlib
import os
import random
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(HERE, "sha256_cli")

NIST = [
    (b"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    (b"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
    (b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
     "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"),
    (b"abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmnhijklmnoijklmnopjklmnopqklmnopqrlmnopqrsmnopqrstnopqrstu",
     "cf5b16a778af8380036ce59e7b0492370b249b11e8f07a51afac45037afee9d1"),
]
MILLION_A = "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0"


def c_hash(data):
    return subprocess.run([CLI], input=data, capture_output=True, check=True).stdout.decode().strip()


class SHA256(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["cc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic", "-o", CLI,
                        os.path.join(HERE, "sha256_cli.c")], check=True)

    def test_nist_vectors(self):
        for msg, want in NIST:
            self.assertEqual(c_hash(msg), want, msg[:20])
            self.assertEqual(hashlib.sha256(msg).hexdigest(), want)

    def test_million_a(self):
        out = subprocess.run([CLI, "-a", "1000000"], capture_output=True, check=True).stdout.decode().strip()
        self.assertEqual(out, MILLION_A)

    def test_every_length_0_to_200(self):
        rnd = random.Random(20261112)
        for n in range(201):
            data = bytes(rnd.randrange(256) for _ in range(n))
            self.assertEqual(c_hash(data), hashlib.sha256(data).hexdigest(), n)

    def test_boundaries_named(self):
        for n in (55, 56, 63, 64, 65, 119, 120, 127, 128):
            data = b"x" * n
            self.assertEqual(c_hash(data), hashlib.sha256(data).hexdigest(), n)

    def test_large_random(self):
        rnd = random.Random(7)
        for n in (4096, 65537, 300001):
            data = bytes(rnd.randrange(256) for _ in range(n))
            self.assertEqual(c_hash(data), hashlib.sha256(data).hexdigest(), n)


if __name__ == "__main__":
    unittest.main()
