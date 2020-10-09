from unittest import TestCase

from kubetools.config import _conditions_match, _legacy_conditions_match


def _test_conditions(
    matcher,
    conditions,
    desired_value,
    context=None,
    namespace=None,
    dev=False,
    test=False,
):
    result = matcher(conditions, context, namespace, dev, test)
    assert result == desired_value


def _test_condition_matcher(*args, **kwargs):
    _test_conditions(_conditions_match, *args, **kwargs)


def _test_legacy_condition_matcher(*args, **kwargs):
    _test_conditions(_legacy_conditions_match, *args, **kwargs)


class TestConditionMatching(TestCase):
    def test_no_conditions(self):
        _test_condition_matcher(None, True)

    def test_no_dev_conditions(self):
        conditions = {'dev': False}
        _test_condition_matcher(conditions, False, dev=True)

    def test_no_test_conditions(self):
        conditions = {'test': False}
        _test_condition_matcher(conditions, False, test=True)

    def test_deploy_true_conditions(self):
        conditions = {'deploy': True}
        _test_condition_matcher(conditions, True)

    def test_deploy_namespace_context_conditions(self):
        conditions = {'deploy': [
            {'namespace': 'another-namespace', 'context': 'another-context'},
            {'namespace': 'a-namespace', 'context': 'a-context'},
        ]}
        _test_condition_matcher(
            conditions,
            True,
            namespace='a-namespace',
            context='a-context',
        )

    def test_deploy_context_conditions(self):
        conditions = {'deploy': [
            {'context': 'a-context'},
        ]}
        _test_condition_matcher(
            conditions,
            True,
            namespace='a-namespace',
            context='a-context',
        )

    def test_deploy_namespace_conditions(self):
        conditions = {'deploy': [
            {'namespace': 'a-namespace'},
        ]}
        _test_condition_matcher(
            conditions,
            True,
            namespace='a-namespace',
            context='a-context',
        )

    def test_deploy_not_context_conditions(self):
        conditions = {'deploy': [
            {'not_context': 'a-context'},
        ]}
        _test_condition_matcher(
            conditions,
            False,
            namespace='a-namespace',
            context='a-context',
        )

    def test_deploy_not_namespace_conditions(self):
        conditions = {'deploy': [
            {'not_namespace': 'a-namespace'},
        ]}
        _test_condition_matcher(
            conditions,
            False,
            namespace='a-namespace',
            context='a-context',
        )


class TestLegacyConditionMatching(TestCase):
    def test_no_conditions(self):
        _test_legacy_condition_matcher(None, True)

    def test_dev_conditions(self):
        _test_legacy_condition_matcher({'dev': True}, True, dev=True)
