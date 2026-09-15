import io
import json
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "mise-tasks" / "mise" / "tool-links"
spec = spec_from_loader("tool_links", SourceFileLoader("tool_links", str(SCRIPT)))
tool_links = module_from_spec(spec)
spec.loader.exec_module(tool_links)


def row(tool):
    return {
        "tool": tool,
        "backend": None,
        "homepage": None,
        "repository": None,
        "plugin_repository": None,
        "project_url": None,
        "mise_docs": None,
        "registry": None,
        "sources": [],
        "metadata_error": None,
    }


class ToolLinksTests(unittest.TestCase):
    def test_pypi_code_of_conduct_is_not_source_and_homepage_beats_docs(self):
        data = {"info": {"project_urls": {
            "Code of Conduct": "https://docs.ansible.com/ansible/latest/community/code_of_conduct.html",
            "Documentation": "https://docs.ansible.com/ansible-core/",
            "Homepage": "https://ansible.com/",
            "Source Code": "https://github.com/ansible/ansible/",
        }}}
        home, repo = tool_links.metadata_links("pypi", data)
        self.assertEqual(home, "https://ansible.com/")
        self.assertEqual(repo, "https://github.com/ansible/ansible")

    def test_npm_git_repository_and_homepage_fragment(self):
        data = {
            "homepage": "https://github.com/openai/codex#readme",
            "repository": {"url": "git+https://github.com/openai/codex.git", "directory": "codex-cli"},
        }
        self.assertEqual(tool_links.metadata_links("npm", data), (
            "https://github.com/openai/codex#readme", "https://github.com/openai/codex",
        ))
        self.assertEqual(tool_links.clean_url("git@github.com:openai/codex.git", repository=True), "https://github.com/openai/codex")

    def test_aqua_uses_registry_repository_fields_and_does_not_guess(self):
        packages = {
            "vendor/cli": {"repo_owner": "actual-owner", "repo_name": "actual-repo"},
            "1password/cli": {"type": "http"},
        }
        result = tool_links.resolve(row("aqua:vendor/cli"), packages, False)
        self.assertEqual(result["repository"], "https://github.com/actual-owner/actual-repo")
        unknown = tool_links.resolve(row("aqua:1password/cli"), packages, False)
        self.assertIsNone(unknown["repository"])
        self.assertEqual(unknown["status"], "unresolved")

    def test_cargo_git_url_short_circuits_package_api(self):
        with patch.object(tool_links, "fetch_json") as fetch:
            result = tool_links.resolve(row("cargo:https://github.com/josh-project/josh.git"), {}, False)
        self.assertEqual(result["repository"], "https://github.com/josh-project/josh")
        self.assertIsNone(result["registry"])
        self.assertEqual(result["status"], "ok")
        fetch.assert_not_called()

    def test_shorthand_uses_mise_selected_backend(self):
        with patch.object(tool_links, "run_command", return_value=json.dumps({
            "backend": "npm:actual-package", "url": None,
        })) as command, patch.object(tool_links, "fetch_json", return_value={
            "repository": "https://gitlab.com/example/actual-package.git",
        }) as fetch:
            result = tool_links.resolve(row("short-name"), {}, False)
        command.assert_called_once_with("mise", "tool", "--json", "short-name")
        fetch.assert_called_once_with("https://registry.npmjs.org/actual-package/latest", False)
        self.assertEqual(result["backend"], "npm:actual-package")
        self.assertEqual(result["repository"], "https://gitlab.com/example/actual-package")

    def test_plugin_repository_is_separate_from_tool_source(self):
        result = tool_links.resolve(row("asdf:https://gitlab.com/wt0f/asdf-ripgrep"), {}, False)
        self.assertEqual(result["plugin_repository"], "https://gitlab.com/wt0f/asdf-ripgrep")
        self.assertIsNone(result["repository"])
        self.assertEqual(result["status"], "plugin-only")

    def test_core_java_exposes_upstream_and_mise_docs_separately(self):
        def command(*args):
            if args[0] == "mise":
                return json.dumps({"backend": "core:java", "url": None})
            return json.dumps({"html_url": "https://github.com/openjdk/jdk", "homepage": ""})

        with patch.object(tool_links, "run_command", side_effect=command):
            result = tool_links.resolve(row("java"), {}, False)
        self.assertEqual(result["repository"], "https://github.com/openjdk/jdk")
        self.assertEqual(result["mise_docs"], "https://mise.jdx.dev/lang/java.html")
        self.assertIsNone(result["homepage"])
        self.assertIn("core upstream: openjdk/jdk", result["sources"])

    def test_packslip_host_and_monorepo_paths(self):
        for tool in ("packslip:github.com/jdx/hk", "packslip:jdx/hk", "packslip:github.com/jdx/hk/tools/subtool"):
            with self.subTest(tool=tool):
                result = tool_links.resolve(row(tool), {}, False)
                self.assertEqual(result["repository"], "https://github.com/jdx/hk")
        result = tool_links.resolve(row("packslip:tool.example.com/tools/cli"), {}, False)
        self.assertEqual(result["homepage"], "https://tool.example.com/tools/cli")
        self.assertIsNone(result["repository"])

    def test_registry_project_candidate_does_not_replace_plugin_backend(self):
        registry = {"neovim": {"backends": ["vfox:mise-plugins/vfox-neovim", "aqua:neovim/neovim"]}}
        aqua = {"neovim/neovim": {"repo_owner": "neovim", "repo_name": "neovim"}}
        with patch.object(tool_links, "run_command", return_value=json.dumps({
            "backend": "vfox:mise-plugins/vfox-neovim", "url": None,
        })):
            result = tool_links.resolve(row("neovim"), aqua, False, registry)
        self.assertEqual(result["backend"], "vfox:mise-plugins/vfox-neovim")
        self.assertEqual(result["plugin_repository"], "https://github.com/mise-plugins/vfox-neovim")
        self.assertEqual(result["repository"], "https://github.com/neovim/neovim")
        self.assertIn("mise registry project candidate: aqua:neovim/neovim", result["sources"])

    def test_forgejo_custom_host(self):
        with patch.object(tool_links, "run_command", return_value=json.dumps({
            "backend": "forgejo:owner/project", "tool_options": {"api_url": "https://forgejo.example/api/v1"},
        })):
            result = tool_links.resolve(row("forgejo:owner/project"), {}, False)
        self.assertEqual(result["repository"], "https://forgejo.example/owner/project")

    def test_go_vanity_module_reads_matching_import_metadata(self):
        html = b'''<html><head>
          <meta name="go-import" content="unrelated.example/mod git https://example.com/wrong.git">
          <meta name="go-import" content="golang.org/x/tools git https://go.googlesource.com/tools">
          </head></html>'''
        with patch.object(tool_links, "urlopen", return_value=io.BytesIO(html)):
            repo = tool_links.go_repository("golang.org/x/tools/gopls")
        self.assertEqual(repo, "https://go.googlesource.com/tools")

    def test_metadata_error_is_reported_without_stopping_other_tools(self):
        with patch.object(tool_links, "fetch_json", side_effect=OSError("network unavailable")):
            failed = tool_links.resolve(row("npm:example-package"), {}, False)
            direct = tool_links.resolve(row("github:openai/codex"), {}, False)
        self.assertEqual(failed["status"], "error")
        self.assertEqual(failed["metadata_error"], "network unavailable")
        self.assertEqual(direct["repository"], "https://github.com/openai/codex")

    def test_json_cache_avoids_network_and_refresh_reloads(self):
        def response(*args, **kwargs):
            return io.BytesIO(b'{"repository":"https://github.com/openai/codex"}')

        with tempfile.TemporaryDirectory() as directory, patch.object(tool_links, "CACHE_ROOT", Path(directory)), patch.object(tool_links, "urlopen", side_effect=response) as network:
            first = tool_links.fetch_json("https://registry.npmjs.org/example/latest", False)
            cached = tool_links.fetch_json("https://registry.npmjs.org/example/latest", False)
            refreshed = tool_links.fetch_json("https://registry.npmjs.org/example/latest", True)
        self.assertEqual(first, cached)
        self.assertEqual(first, refreshed)
        self.assertEqual(network.call_count, 2)


if __name__ == "__main__":
    unittest.main()
