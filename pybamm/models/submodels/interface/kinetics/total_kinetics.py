#
# Total kinetics class, summing up contributions from all reactions
#
import pybamm


class TotalKinetics(pybamm.BaseSubModel):
    """
    Total kinetics class, summing up contributions from all reactions

    Parameters
    ----------
    param :
        model parameters
    domain : str
        The domain to implement the model, either: 'Negative' or 'Positive'.
    reaction : str
        The name of the reaction being implemented
    options: dict
        A dictionary of options to be passed to the model.
        See :class:`pybamm.BaseBatteryModel`

    **Extends:** :class:`pybamm.interface.BaseInterface`
    """

    def __init__(self, param, chemistry, options):
        super().__init__(param, options=options)
        self.chemistry = chemistry

    def get_coupled_variables(self, variables):
        """
        Get variables associated with interfacial current over the whole cell domain
        This function also creates the "total source term" variables by summing all
        the reactions
        """
        param = self.param

        i_typ = param.i_typ
        L_x = param.L_x

        if self.chemistry == "lithium-ion":
            reaction_names = ["", "SEI ", "lithium plating "]
            phase_names = [""] * 3  # primary phases
            if self.options["particle phases"] != "1":
                reaction_names.append("secondary ")
                phase_names.append("secondary ")

        # Create separate 'new_variables' so that variables only get updated once
        # everything is computed
        new_variables = variables.copy()

        # Initialize "total reaction" variables
        # These will get populated by each reaction, and then used
        # later by "set_rhs" or "set_algebraic", which ensures that we always have
        # added all the necessary variables by the time the sum is used
        new_variables.update(
            {
                "Sum of electrolyte reaction source terms": 0,
                "Sum of positive electrode electrolyte reaction source terms": 0,
                "Sum of x-averaged positive electrode "
                "electrolyte reaction source terms": 0,
                "Sum of interfacial current densities": 0,
                "Sum of positive electrode interfacial current densities": 0,
                "Sum of x-averaged positive electrode interfacial current densities": 0,
            }
        )
        if not self.half_cell:
            new_variables.update(
                {
                    "Sum of negative electrode electrolyte reaction source terms": 0,
                    "Sum of x-averaged negative electrode "
                    "electrolyte reaction source terms": 0,
                    "Sum of negative electrode interfacial current densities": 0,
                    "Sum of x-averaged negative electrode interfacial current densities"
                    "": 0,
                }
            )
        for reaction_name, phase_name in zip(reaction_names, phase_names):
            if phase_name == "":
                j_n_scale = param.n.prim.j_scale
                j_p_scale = param.p.prim.j_scale
            elif phase_name == "secondary ":
                j_n_scale = param.n.sec.j_scale
                j_p_scale = param.p.sec.j_scale

            j_p_av = variables[
                f"X-averaged positive electrode {reaction_name}"
                "interfacial current density"
            ]

            zero_s = pybamm.FullBroadcast(0, "separator", "current collector")
            j_p = variables[
                f"Positive electrode {reaction_name}interfacial current density"
            ]

            if self.half_cell:
                j = pybamm.concatenation(zero_s, j_p)
                j_dim = pybamm.concatenation(zero_s, j_p_scale * j_p)
            else:
                j_n_av = variables[
                    f"X-averaged negative electrode {reaction_name}"
                    "interfacial current density"
                ]
                j_n = variables[
                    f"Negative electrode {reaction_name}interfacial current density"
                ]
                j = pybamm.concatenation(j_n, zero_s, j_p)
                j_dim = pybamm.concatenation(j_n_scale * j_n, zero_s, j_p_scale * j_p)

            if reaction_name not in ["SEI ", "lithium plating "]:
                j0_p = variables[
                    f"Positive electrode {reaction_name}exchange current density"
                ]

                if self.half_cell:
                    j0 = pybamm.concatenation(zero_s, j0_p)
                    j0_dim = pybamm.concatenation(zero_s, j_p_scale * j0_p)
                else:
                    j0_n = variables[
                        f"Negative electrode {reaction_name}exchange current density"
                    ]
                    j0 = pybamm.concatenation(j0_n, zero_s, j0_p)
                    j0_dim = pybamm.concatenation(
                        j_n_scale * j0_n, zero_s, j_p_scale * j0_p
                    )
                new_variables.update(
                    {
                        f"{reaction_name}interfacial ".capitalize()
                        + "current density": j,
                        f"{reaction_name}interfacial ".capitalize()
                        + "current density [A.m-2]": j_dim,
                        f"{reaction_name}interfacial ".capitalize()
                        + "current density per volume [A.m-3]": i_typ / L_x * j,
                        f"{reaction_name}exchange ".capitalize()
                        + "current density": j0,
                        f"{reaction_name}exchange ".capitalize()
                        + "current density [A.m-2]": j0_dim,
                        f"{reaction_name}exchange ".capitalize()
                        + "current density per volume [A.m-3]": i_typ / L_x * j0,
                    }
                )

            # Sum variables
            if pybamm.xyz_average(j_p).id == pybamm.Scalar(0).id:
                a_p = j_p
            else:
                a_p = new_variables[
                    f"Positive electrode {phase_name}surface area to volume ratio"
                ]

            if self.chemistry == "lithium-ion":
                # Both the main reaction current contribute to the electrolyte reaction
                # current
                s_n, s_p = 1, 1
            # elif self.reaction == "lead-acid main":
            #     s_n, s_p = self.param.n.s_plus_S, self.param.p.s_plus_S
            # elif self.reaction == "lead-acid oxygen":
            #     s_n, s_p = self.param.s_plus_Ox, self.param.s_plus_Ox
            # else:
            #     s_n, s_p = 0, 0
            if self.half_cell:
                a_n = pybamm.Scalar(1)
                a = pybamm.concatenation(zero_s, a_p)
                s = pybamm.concatenation(
                    zero_s,
                    pybamm.FullBroadcast(
                        s_p, "positive electrode", "current collector"
                    ),
                )
            else:
                if pybamm.xyz_average(j_n).id == pybamm.Scalar(0).id:
                    a_n = j_n
                else:
                    a_n = new_variables[
                        f"Negative electrode {phase_name}surface area to volume ratio"
                    ]
                a = pybamm.concatenation(a_n, zero_s, a_p)
                s = pybamm.concatenation(
                    pybamm.FullBroadcast(
                        s_n, "negative electrode", "current collector"
                    ),
                    zero_s,
                    pybamm.FullBroadcast(
                        s_p, "positive electrode", "current collector"
                    ),
                )

            # Override print_name
            j.print_name = "J"
            a.print_name = "a"
            j_p.print_name = "j_p"

            new_variables["Sum of electrolyte reaction source terms"] += a * s * j
            new_variables[
                "Sum of positive electrode electrolyte reaction source terms"
            ] += (a_p * s_p * j_p)
            new_variables[
                "Sum of x-averaged positive electrode electrolyte reaction source terms"
            ] += pybamm.x_average(a_p * s_p * j_p)

            new_variables["Sum of interfacial current densities"] += j
            new_variables[
                "Sum of positive electrode interfacial current densities"
            ] += j_p
            new_variables[
                "Sum of x-averaged positive electrode interfacial current densities"
            ] += j_p_av

            if not self.half_cell:
                j_n.print_name = "j_n"
                new_variables[
                    "Sum of negative electrode electrolyte reaction source terms"
                ] += (a_n * s_n * j_n)
                new_variables[
                    "Sum of x-averaged negative electrode electrolyte "
                    "reaction source terms"
                ] += pybamm.x_average(a_n * s_n * j_n)
                new_variables[
                    "Sum of negative electrode interfacial current densities"
                ] += j_n
                new_variables[
                    "Sum of x-averaged negative electrode interfacial current densities"
                ] += j_n_av

        variables.update(new_variables)

        return variables