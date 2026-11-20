"""Static T0 contracts; never imports or instantiates model code."""
import copy
import unittest
from integration.structure.t0_contract import check_header, validate_execution_lock, expected_shapes


class T0Tests(unittest.TestCase):
    def setUp(self):
        self.config=dict(hidden_size=2,intermediate_size=4,num_hidden_layers=1,
                         vocab_size=5,max_position_embeddings=8,
                         max_2d_position_embeddings=8,type_vocab_size=2,max_source_length=3)
        self.header={k:dict(shape=v,dtype='F32') for k,v in expected_shapes(self.config).items()}

    def test_complete_header(self):
        self.assertTrue(check_header(self.header,self.config)['strict_compatible'])

    def test_missing_auxiliary_is_not_silently_allowed(self):
        del self.header['bert.pooler.dense.weight']
        result=check_header(self.header,self.config)
        self.assertFalse(result['strict_compatible'])
        self.assertIn('bert.pooler.dense.weight',result['missing'])

    def test_missing_layout_or_order_head(self):
        for key in ['bert.embeddings.x_position_embeddings.weight','cls.predictions.bias']:
            h=copy.deepcopy(self.header);del h[key]
            self.assertFalse(check_header(h,self.config)['strict_compatible'])

    def test_wrong_shape_and_dtype(self):
        self.header['cls.predictions.bias']['shape']=[4]
        self.header['bert.embeddings.word_embeddings.weight']['dtype']='F16'
        result=check_header(self.header,self.config)
        self.assertFalse(result['strict_compatible'])
        self.assertEqual(len(result['mismatches']),2)

    def test_unexpected_tensor_rejected_without_implicit_whitelist(self):
        self.header['unknown.weight']=dict(shape=[2],dtype='F32')
        self.assertFalse(check_header(self.header,self.config)['strict_compatible'])

    def test_floating_or_unverified_lock_rejected(self):
        with self.assertRaises(ValueError):validate_execution_lock(dict(revision='main',sha256='a'*64,locally_verified=True))
        with self.assertRaises(ValueError):validate_execution_lock(dict(revision='a'*40,sha256=None,locally_verified=True))
        with self.assertRaises(ValueError):validate_execution_lock(dict(revision='a'*40,sha256='b'*64,locally_verified=False))

    def test_pinned_verified_lock(self):
        validate_execution_lock(dict(revision='a'*40,sha256='b'*64,locally_verified=True))


if __name__=='__main__':unittest.main()
