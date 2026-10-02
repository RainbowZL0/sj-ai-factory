# Simulation

## Rules of one simulated second

`FactorySim.step(changes)` does these steps in this order:

1. **Switch recipes.** Only idle machines (no batch running, no changeover going on) can switch. Asking a busy machine to switch is an error, because it would mean the caller has a bug. Switching to a different recipe starts a changeover of `changeover_time` seconds, during which the machine makes nothing and uses no power. Stopping needs no changeover; starting again after a stop does.
2. **Start batches.** Every idle machine that has a recipe starts if the stock covers the inputs. Inputs are taken now. Machines are served in list order.
3. **Use power.** Running machines use `power_kw × 1 s` of energy.
4. **Advance one second.** Changeovers count down. Batches that reach zero put their outputs into stock.
5. **Settle due orders.** Orders whose due time has arrived ship whatever stock exists. Missing units cost `shortfall_penalty` each.
6. **Settle cash.** Cash changes by revenue − penalty − energy − storage − rent.

All machines share one warehouse, so the scenario needs no links between machines. The real connections are the material flow chart (`material_flow.png`), drawn from the recipes.

A change meant only to make this faster must give identical results: compare it second by second with the old code on several seeds, with random plans, and check that keep still makes 52,050 on seed 0.

## The default scenario (`scenarios/default.yaml`)

- 5000 s per episode, 50 random orders for Motors and Frames, seeded at `reset()`.
- 25 machines: 6 casters, 14 constructors, 5 assemblers.
- Changeover 30 s. Motor sells for 800 (penalty 400 per missing unit), Frame for 300 (penalty 150). Rent 0.5 per second; energy is free.
- Ore stock is 0, so the casters never run. Ingots start at 99,999, so they never run out.
- Keep (every machine stays on its starting recipe) never runs PlateAssemble or FrameFinal, so it fills no Frame orders.

## Not modelled yet

- Buying raw materials.
- Orders appearing during the episode. All orders are known at the start.
- Machine breakdowns.

Each would be a field in `spec.py` plus a few lines in `FactorySim.step`.
