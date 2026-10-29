"""SDPA with explicit KV repetition, including efficient kernels on Windows.

Transformers 4.57 enables native GQA on CUDA without a mask. PyTorch 2.8's
Windows build lacks Flash Attention; native GQA can therefore select the
quadratic math kernel. Repeating KV heads preserves attention semantics and
allows the available memory-efficient kernel. No installed package is patched.
"""


def repeated_kv_sdpa(module, query, key, value, attention_mask, dropout=0.0,
                     scaling=None, is_causal=None, **kwargs):
    import torch

    if kwargs.get("output_attentions") or kwargs.get("head_mask") is not None:
        raise ValueError("Repeated-KV SDPA does not return attention weights or support head masks")
    groups = getattr(module, "num_key_value_groups", 1)
    if groups > 1:
        from transformers.integrations.sdpa_attention import repeat_kv

        key, value = repeat_kv(key, groups), repeat_kv(value, groups)
    if attention_mask is not None and attention_mask.ndim == 4:
        attention_mask = attention_mask[:, :, :, :key.shape[-2]]
    if is_causal is None:
        is_causal = query.shape[2] > 1 and attention_mask is None and getattr(module, "is_causal", True)
    if torch.jit.is_tracing() and isinstance(is_causal, torch.Tensor):
        is_causal = is_causal.item()
    output = torch.nn.functional.scaled_dot_product_attention(
        query, key, value, attn_mask=attention_mask, dropout_p=dropout,
        scale=scaling, is_causal=is_causal,
    )
    return output.transpose(1, 2).contiguous(), None


def register_repeated_kv_sdpa():
    """Register a separate attention name and the identical SDPA causal-mask rule."""
    from transformers import AttentionInterface
    from transformers.masking_utils import AttentionMaskInterface, sdpa_mask

    AttentionInterface.register("sdpa_repeated_kv", repeated_kv_sdpa)
    AttentionMaskInterface.register("sdpa_repeated_kv", sdpa_mask)
