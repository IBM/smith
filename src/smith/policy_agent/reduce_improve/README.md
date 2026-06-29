## Done
- Find unreachable redundancy by graph
- Find dead route by graph 
```python detect_redundancy.py```
- Use regal to get policy advice

```
brew install regal
regal lint policies
```
You can configure the standards in `.regal.yaml`
```Run tests: 
regal lint policy/
```

## TBD
- Design and implement other algorithms for more kinds of redundancies
