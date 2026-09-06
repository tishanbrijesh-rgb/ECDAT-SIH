"""Independent evaluator arithmetic and metadata checks, without downloads."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import benchmark_external
from scripts.benchmark_external import (_finding_line, _in_scope_findings,
                                        _validate_manifest, compare)
from tests import test_precision as precision


class BenchmarkMetricTests(unittest.TestCase):
    def label(self, **changes):
        return {'file': 'app.java', 'line': 1, 'algorithm': 'AES',
                'usage': 'encryption', 'key_size': 256, **changes}

    def test_duplicates_are_false_positives(self):
        result = compare([self.label()], [self.label(), self.label()])
        self.assertEqual((result['tp'], result['fp'], result['fn']), (1, 1, 0))
        self.assertEqual(result['precision'], 0.5)

    def test_correct_algorithm_does_not_hide_bad_metadata(self):
        result = compare([self.label()], [self.label(usage='unknown', key_size=None)])
        self.assertEqual(result['precision'], 1)
        self.assertEqual(result['usage_accuracy_over_expected'], 0)
        self.assertEqual(result['known_key_size_accuracy_over_expected'], 0)

    def test_missed_key_size_is_not_removed_from_denominator(self):
        result = compare([self.label()], [])
        self.assertEqual(result['fn'], 1)
        self.assertEqual(result['known_key_size_accuracy_over_expected'], 0)

    def test_absent_key_labels_are_unavailable_not_perfect(self):
        result = compare([self.label(key_size=None)], [self.label(key_size=None)])
        self.assertIsNone(result['known_key_size_accuracy_over_expected'])

    def test_empty_negative_metrics_are_unavailable(self):
        result = compare([], [])
        self.assertIsNone(result['precision'])
        self.assertIsNone(result['recall'])
        self.assertIsNone(result['f1'])

    def test_duplicate_metadata_uses_one_joint_matching(self):
        expected = [self.label(usage='hashing', key_size=128),
                    self.label(usage='encryption', key_size=256)]
        actual = [self.label(usage='hashing', key_size=256),
                  self.label(usage='encryption', key_size=128)]
        result = compare(expected, actual)
        self.assertEqual(result['usage_correct'] + result['known_key_size_correct'], 2)
        self.assertNotEqual((result['usage_correct'], result['known_key_size_correct']), (2, 2))
        self.assertEqual(result['metadata_pair_correct'], 0)
        self.assertEqual(result['metadata_pair_accuracy_over_expected'], 0)

    def test_line_ignores_unlocated_evidence(self):
        finding = {'evidence_list': [
            {'evidence': {'line': 7}}, {'evidence': {}}, {'evidence': {'line': None}},
        ]}
        self.assertEqual(_finding_line(finding), 7)

    def test_taxonomy_ignores_out_of_scope_algorithms_only(self):
        findings = [{'algorithm': 'SHA-256'}, {'algorithm': 'AES'}]
        self.assertEqual(_in_scope_findings(findings, ['SHA-256']), [findings[0]])
        result = compare([], [{'file': 'x', 'line': 1, 'algorithm': 'SHA-256',
                               'usage': 'hashing', 'key_size': None}])
        self.assertEqual(result['fp'], 1)


class ManifestValidationTests(unittest.TestCase):
    def source(self, **changes):
        return {'name': 'sample', 'checkout': 'checkout', 'path': 'checkout/source.py',
                'revision': 'a' * 40, 'sha256': 'b' * 64, 'operations': [], **changes}

    def manifest(self, *sources):
        return {'schema': 1, 'algorithms': ['AES'],
                'sources': list(sources or (self.source(),))}

    def test_rejects_traversal_and_absolute_paths(self):
        for path in ('../source.py', 'checkout/../source.py', 'C:\\source.py', '/source.py'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                _validate_manifest(self.manifest(self.source(path=path)))

    def test_falsey_and_non_string_paths_are_rejected(self):
        with self.assertRaises(ValueError):
            benchmark_external.run({})
        for value in (None, 0, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _validate_manifest(self.manifest(self.source(path=value)))

    def test_rejects_duplicate_reserved_and_separated_names(self):
        invalid_manifests = [
            self.manifest(self.source(), self.source(name='SAMPLE')),
            self.manifest(self.source(name='mixed')),
            self.manifest(self.source(name='a/b')),
            self.manifest(self.source(name='a\\b')),
            self.manifest(self.source(name='CON')),
        ]
        for manifest in invalid_manifests:
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                _validate_manifest(manifest)

    def test_rejects_source_outside_checkout(self):
        with self.assertRaises(ValueError):
            _validate_manifest(self.manifest(self.source(path='other/source.py')))

    def test_stages_the_bytes_that_were_hashed(self):
        with tempfile.TemporaryDirectory() as root_dir, tempfile.TemporaryDirectory() as stage_dir:
            root = Path(root_dir)
            checkout = root / 'checkout'
            checkout.mkdir()
            source_path = checkout / 'source.py'
            original = b'original bytes'
            source_path.write_bytes(original)
            source = self.source(sha256=hashlib.sha256(original).hexdigest())
            original_read = Path.read_bytes

            def read_then_replace(path):
                data = original_read(path)
                source_path.write_bytes(b'replaced after read')
                return data

            with mock.patch.object(benchmark_external, 'ROOT', root), \
                    mock.patch.object(benchmark_external, '_verify_revision'), \
                    mock.patch.object(Path, 'read_bytes', read_then_replace):
                relative = benchmark_external._stage_source(source, stage_dir)
            self.assertEqual(source_path.read_bytes(), b'replaced after read')
            self.assertEqual((Path(stage_dir) / relative).read_bytes(), original)


class ExternalBugRegressionTests(unittest.TestCase):
    def test_nested_hash_and_aead_names_do_not_change_primitive_usage(self):
        from scanner.collectors.rule_collector import _usage
        self.assertEqual(_usage('ec.ECDSA(hashes.SHA256())', 'ECDSA'), 'signature')
        self.assertEqual(_usage('AES.encrypt_and_digest(data)', 'AES'), 'encryption')
        self.assertEqual(_usage('AES.decrypt_and_verify(data)', 'AES'), 'encryption')

    def scan(self, source, filename='example.py'):
        return precision.PrecisionTests().scan_fixture(source, filename)[0]

    def test_dynamic_hmac_preserves_known_mac_without_guessing_digest(self):
        result = self.scan('import hmac\nhmac.new(key, digestmod=runtime_choice)')
        self.assertEqual(len(result), 1)
        self.assertEqual((result[0]['algorithm'], result[0]['usage']), ('HMAC', 'unknown'))

    def test_java_digest_declaration_is_not_an_operation(self):
        result = self.scan('public class Md5Crypt {\nstatic final String MD5_PREFIX="x";\n'
                           'public static String md5Crypt(byte[] data) {\nreturn "";\n}\n}', 'Example.java')
        self.assertEqual(result, [])

    def test_apache_wrapper_call_not_declaration(self):
        result = self.scan('package org.apache.commons.codec.digest;\n'
                           'public static String apr1Crypt(byte[] data) {\n'
                           'return apr1Crypt(data, salt);\n}', 'Example.java')
        self.assertEqual(len(result), 1)
        self.assertEqual((result[0]['algorithm'], result[0]['usage']), ('MD5', 'hashing'))

    def test_java_sha_wrappers_and_underscore_selectors_are_operations(self):
        source = ('new SHA1Digest();\nSHA256Digest.newInstance();\nnew SHA512Digest();\n'
                  'getDigest(MessageDigestAlgorithms.SHA_1);\n'
                  'getDigest(MessageDigestAlgorithms.SHA_256);\n'
                  'getDigest(MessageDigestAlgorithms.SHA_512);\n')
        result = self.scan(source, 'Example.java')
        self.assertEqual(sorted((item['evidence_list'][0]['evidence']['line'], item['algorithm'])
                                for item in result),
                         [(1, 'SHA-1'), (2, 'SHA-256'), (3, 'SHA-512'),
                          (4, 'SHA-1'), (5, 'SHA-256'), (6, 'SHA-512')])

    def test_java_constants_conditions_and_truncated_sha512_are_not_operations(self):
        source = ('static final String SHA_256 = "SHA-256";\n'
                  'if (salt.startsWith(SHA512_PREFIX)) {}\n'
                  'if (oid.equals(NISTObjectIdentifiers.id_sha512)) {}\n'
                  'new SHA512tDigest(224);\nsha512_256(data);\nSHA512224(data);\n')
        result = self.scan(source, 'Example.java')
        self.assertEqual([item for item in result
                          if item['algorithm'] in {'SHA-1', 'SHA-256', 'SHA-512'}], [])

    def test_java_hash_declarations_and_nested_hmac_are_not_hash_operations(self):
        source = ('private SHA1()\nprivate SHA256() {}\nSHA1Digest() {}\n'
                  'SHA1Digest() throws Exception {\n'
                  'MessageDigest getSha256Digest();\n'
                  'MessageDigest getSha256Digest() {\n'
                  'default MessageDigest getSha256Digest() {\n'
                  'new HMac(new SHA1Digest());\nnew OldHMac(new SHA512Digest());\n')
        self.assertEqual(self.scan(source, 'Example.java'), [])

    def test_java_message_digest_common_aliases_are_operations(self):
        source = ('MessageDigest.getInstance("SHA1");\n'
                  'MessageDigest.getInstance("SHA256");\n'
                  'MessageDigest.getInstance("SHA512");\n')
        result = self.scan(source, 'Example.java')
        self.assertEqual(sorted((item['evidence_list'][0]['evidence']['line'], item['algorithm'])
                                for item in result),
                         [(1, 'SHA-1'), (2, 'SHA-256'), (3, 'SHA-512')])

    def test_java_returned_named_digest_call_is_an_operation(self):
        result = self.scan('return sha256Hex(data);', 'Example.java')
        self.assertEqual([(item['algorithm'], item['usage']) for item in result],
                         [('SHA-256', 'hashing')])

    def test_java_condition_does_not_hide_a_real_non_hash_operation(self):
        result = self.scan('if (Cipher.getInstance("AES/GCM/NoPadding") != null) {}',
                           'Example.java')
        self.assertEqual([(item['algorithm'], item['usage']) for item in result],
                         [('AES', 'encryption')])
