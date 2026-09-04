"""Small adversarial cases independent of the bundled demonstration corpus."""
import unittest
from unittest.mock import mock_open, patch

from backend.services.confidence import score_finding
from scanner.collectors.dep_collector import DepCollector


class ConfidenceRegressionTests(unittest.TestCase):
    def test_duplicate_sources_do_not_inflate_confidence(self):
        self.assertEqual(
            score_finding({"sources": ["ast", "ast", "ast"]}),
            score_finding({"sources": ["ast"]}),
        )

    def test_duplicate_sources_do_not_change_conflict_score(self):
        self.assertEqual(
            score_finding({"sources": ["ast", "rule", "ast"], "conflict": True}),
            score_finding({"sources": ["ast", "rule"], "conflict": True}),
        )


class DependencyRegressionTests(unittest.TestCase):
    def requirements(self, text):
        with patch("os.path.isfile", return_value=True), patch("builtins.open", mock_open(read_data=text)):
            return DepCollector().scan_requirements("requirements.txt")

    def pom(self, text):
        with patch("os.path.isfile", return_value=True), patch("builtins.open", mock_open(read_data=text)):
            return DepCollector().scan_pom_xml("pom.xml")

    def test_requirement_comments_markers_and_normalized_names(self):
        for text, package in (
            ("cryptography # application crypto", "cryptography"),
            ('cryptography; python_version >= "3.10"', "cryptography"),
            ("Argon2_CFFI==23.1", "argon2-cffi"),
            ("python-jose[cryptography]>=3", "python-jose"),
        ):
            with self.subTest(text=text):
                assets = self.requirements(text)
                self.assertTrue(assets)
                self.assertEqual({a.evidence["package"] for a in assets}, {package})

    def test_unknown_requirement_does_not_match_prefix(self):
        self.assertEqual(self.requirements("cryptography-impostor==1"), [])

    def test_maven_pairs_coordinates_within_each_dependency(self):
        assets = self.pom('''<project xmlns="http://maven.apache.org/POM/4.0.0">
          <parent><groupId>example</groupId><artifactId>parent</artifactId></parent>
          <artifactId>application</artifactId>
          <dependencies><dependency><groupId>org.bouncycastle</groupId>
            <artifactId>bcprov-jdk18on</artifactId></dependency></dependencies>
        </project>''')
        self.assertTrue(assets)
        self.assertEqual({a.evidence["artifactId"] for a in assets}, {"bcprov-jdk18on"})

    def test_maven_comments_and_plugins_are_not_dependencies(self):
        self.assertEqual(self.pom('''<project>
          <!-- <dependency><groupId>org.bouncycastle</groupId><artifactId>comment</artifactId></dependency> -->
          <build><plugins><plugin><groupId>org.bouncycastle</groupId>
            <artifactId>plugin</artifactId></plugin></plugins></build>
        </project>'''), [])

    def test_maven_lookalike_group_is_not_trusted(self):
        self.assertEqual(self.pom('''<project><dependencies><dependency>
          <groupId>evil.org.bouncycastle.fake</groupId><artifactId>fake</artifactId>
        </dependency></dependencies></project>'''), [])

    def test_malformed_maven_xml_does_not_produce_findings(self):
        self.assertEqual(self.pom("<project><groupId>org.bouncycastle</groupId>"), [])
