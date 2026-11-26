#!/usr/bin/env python3
# msvcsort.py --- faithful port of the (unstable) std::sort of MSVC 8 (VS2005)
#
# Some original SVOX tools sort with std::sort and equal elements end up in
# an implementation defined order.  To create byte identical output the
# exact algorithm (introsort: median-of-9 partition, heap sort fallback,
# insertion sort below 32 elements) is reproduced here.
#
# Licensed under the Apache License, Version 2.0

ISORT_MAX = 32


def _med3(a, f, m, l, lt):
    if lt(a[m], a[f]):
        a[m], a[f] = a[f], a[m]
    if lt(a[l], a[m]):
        a[l], a[m] = a[m], a[l]
    if lt(a[m], a[f]):
        a[m], a[f] = a[f], a[m]


def _median(a, f, m, l, lt):
    if 40 < l - f:
        step = (l - f + 1) // 8
        _med3(a, f, f + step, f + 2 * step, lt)
        _med3(a, m - step, m, m + step, lt)
        _med3(a, l - 2 * step, l - step, l, lt)
        _med3(a, f + step, m, l - step, lt)
    else:
        _med3(a, f, m, l, lt)


def _unguarded_partition(a, first, last, lt):
    mid = first + (last - first) // 2
    _median(a, first, mid, last - 1, lt)
    pf = mid
    pl = pf + 1
    while first < pf and not lt(a[pf - 1], a[pf]) and not lt(a[pf], a[pf - 1]):
        pf -= 1
    while pl < last and not lt(a[pl], a[pf]) and not lt(a[pf], a[pl]):
        pl += 1
    gf = pl
    gl = pf
    while True:
        while gf < last:
            if lt(a[pf], a[gf]):
                pass
            elif lt(a[gf], a[pf]):
                break
            else:
                a[pl], a[gf] = a[gf], a[pl]
                pl += 1
            gf += 1
        while first < gl:
            if lt(a[gl - 1], a[pf]):
                pass
            elif lt(a[pf], a[gl - 1]):
                break
            else:
                pf -= 1
                a[pf], a[gl - 1] = a[gl - 1], a[pf]
            gl -= 1
        if gl == first and gf == last:
            return pf, pl
        if gl == first:
            if pl != gf:
                a[pf], a[pl] = a[pl], a[pf]
            pl += 1
            a[pf], a[gf] = a[gf], a[pf]
            pf += 1
            gf += 1
        elif gf == last:
            gl -= 1
            pf -= 1
            if gl != pf:
                a[gl], a[pf] = a[pf], a[gl]
            pl -= 1
            a[pf], a[pl] = a[pl], a[pf]
        else:
            gl -= 1
            a[gf], a[gl] = a[gl], a[gf]
            gf += 1


def _push_heap(a, first, hole, top, val, lt):
    idx = (hole - 1) // 2
    while top < hole and lt(a[first + idx], val):
        a[first + hole] = a[first + idx]
        hole = idx
        idx = (hole - 1) // 2
    a[first + hole] = val


def _adjust_heap(a, first, hole, bottom, val, lt):
    top = hole
    idx = 2 * hole + 2
    while idx < bottom:
        if lt(a[first + idx], a[first + idx - 1]):
            idx -= 1
        a[first + hole] = a[first + idx]
        hole = idx
        idx = 2 * idx + 2
    if idx == bottom:
        a[first + hole] = a[first + bottom - 1]
        hole = bottom - 1
    _push_heap(a, first, hole, top, val, lt)


def _make_heap(a, first, last, lt):
    bottom = last - first
    hole = bottom // 2
    while 0 < hole:
        hole -= 1
        _adjust_heap(a, first, hole, bottom, a[first + hole], lt)


def _sort_heap(a, first, last, lt):
    while 1 < last - first:
        last -= 1
        val = a[last]
        a[last] = a[first]
        _adjust_heap(a, first, 0, last - first, val, lt)


def _insertion_sort(a, first, last, lt):
    if first == last:
        return
    for nxt in range(first + 1, last):
        val = a[nxt]
        if lt(val, a[first]):
            a[first + 1:nxt + 1] = a[first:nxt]
            a[first] = val
        else:
            hole = nxt
            while lt(val, a[hole - 1]):
                a[hole] = a[hole - 1]
                hole -= 1
            a[hole] = val


def _sort(a, first, last, ideal, lt):
    while True:
        count = last - first
        if not (ISORT_MAX < count and 0 < ideal):
            break
        mf, ms = _unguarded_partition(a, first, last, lt)
        ideal //= 2
        ideal += ideal // 2
        if mf - first < last - ms:
            _sort(a, first, mf, ideal, lt)
            first = ms
        else:
            _sort(a, ms, last, ideal, lt)
            last = mf
    if ISORT_MAX < count:
        _make_heap(a, first, last, lt)
        _sort_heap(a, first, last, lt)
    elif 1 < count:
        _insertion_sort(a, first, last, lt)


def sort(a, lt=lambda x, y: x < y):
    """in-place std::sort(a.begin(), a.end(), lt) as in MSVC 8"""
    _sort(a, 0, len(a), len(a), lt)
    return a
